import logging
import sys
from datetime import datetime

from celery import shared_task, states
from celery.signals import before_task_publish
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def perform_file_set_inference(self, file_set_id, ml_model_id, schema="public"):
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, get_tenant_model
    from apps.classif_ai.services import InferenceService

    # Setting the correct schema
    if connection.schema_name != get_public_schema_name():
        connection.set_schema_to_public()

    if schema != get_public_schema_name():
        tenant = get_tenant_model().objects.get(schema_name=schema)
        connection.set_tenant(tenant, include_public=True)

    try:
        logger.info(f"Schema_name: {schema}, File Set Id: {file_set_id}, Model Id: {ml_model_id}")
        InferenceService(ml_model_id, file_set_id).perform()
    except ValidationError as e:
        # ToDo: justify this pass.
        if "file" in e.message_dict.keys():
            pass
        elif "FileSetInferenceQueue" in e.message_dict.keys():
            self.retry(exc=e, countdown=2**self.request.retries, max_retries=20)
        else:
            raise e
    return


@shared_task(bind=True, ignore_result=True)
def perform_retraining(self, training_session_id, schema="public"):
    from django.db import connection
    from django.db.models import Q
    from django_tenants.utils import get_public_schema_name, get_tenant_model
    from apps.classif_ai.models import TrainingSession, TrainingSessionFileSet, FileRegion
    from apps.classif_ai.helpers import calculate_iou
    from sixsense import settings

    sys.path.append(settings.DS_MODEL_INVOCATION_PATH)
    from retrain import main

    # Setting the correct schema
    if connection.schema_name != get_public_schema_name():
        connection.set_schema_to_public()

    if schema != get_public_schema_name():
        tenant = get_tenant_model().objects.get(schema_name=schema)
        connection.set_tenant(tenant, include_public=True)

    training_session = TrainingSession.objects.get(id=training_session_id)
    if training_session.started_at:
        return
    ml_model = training_session.new_ml_model
    training_session.started_at = datetime.utcnow()
    training_session.save()
    try:
        main(training_session_id, schema)
        training_session.refresh_from_db()
        training_session.finished_at = datetime.utcnow()
        training_session.save()
        ml_model.refresh_from_db()
    except Exception as e:
        ml_model.refresh_from_db()
        if ml_model.status != "user_terminated":
            ml_model.status = "training_failed"
            ml_model.save()
        training_session.refresh_from_db()
        training_session.finished_at = datetime.utcnow()
        training_session.save()
        raise e
    # ToDo: Copy the existing feedback as well for all the file sets
    batch_size = 1000
    qs = TrainingSessionFileSet.objects.filter(
        Q(dataset_train_type="TEST") | Q(dataset_train_type="test"), training_session_id=training_session_id
    )
    total = qs.count()
    ml_model.status = "ready_for_deployment"
    ml_model.save()
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        for tfs in qs[start:end]:
            for file, regions in tfs.defects.items():
                ai_regions = FileRegion.objects.filter(
                    ml_model_id=training_session.new_ml_model_id, file_id=file, is_user_feedback=False
                )
                for region in regions:
                    matching_region = None
                    for ai_region in ai_regions:
                        if ml_model.type == "CLASSIFICATION":
                            if list(ai_region.defects)[0] == list(region["defects"])[0]:
                                matching_region = [ai_region, None]
                        else:
                            iou = calculate_iou(
                                [
                                    region["region"]["coordinates"]["x"],
                                    region["region"]["coordinates"]["y"],
                                    region["region"]["coordinates"]["x"] + region["region"]["coordinates"]["w"],
                                    region["region"]["coordinates"]["y"] + region["region"]["coordinates"]["h"],
                                ],
                                [
                                    ai_region.region["coordinates"]["x"],
                                    ai_region.region["coordinates"]["y"],
                                    ai_region.region["coordinates"]["x"] + ai_region.region["coordinates"]["w"],
                                    ai_region.region["coordinates"]["y"] + ai_region.region["coordinates"]["h"],
                                ],
                            )
                            if iou > 0.4:
                                if matching_region:
                                    if matching_region[1] < iou:
                                        matching_region = [ai_region, iou]
                                else:
                                    matching_region = [ai_region, iou]
                    file_region = FileRegion(
                        file_id=file,
                        ml_model_id=training_session.new_ml_model_id,
                        defects=region["defects"],
                        region=region["region"],
                        is_user_feedback=True,
                    )
                    if matching_region and ml_model.type == "CLASSIFICATION":
                        matching_region[0].classification_correctness = True
                        matching_region[0].save()
                    elif matching_region:
                        file_region.ai_region_id = matching_region[0].id
                        file_region.save()
                    else:
                        file_region.save()
                for ai_region in ai_regions.all():
                    if ml_model.type == "CLASSIFICATION" and ai_region.classification_correctness == None:
                        ai_region.classification_correctness = False
                        ai_region.save()
                    elif ml_model.type != "CLASSIFICATION" and ai_region.detection_correctness == None:
                        ai_region.is_removed = True
                        ai_region.classification_correctness = False
                        ai_region.detection_correctness = False
                        ai_region.save()


@shared_task(bind=True, ignore_result=True)
def stitch_image_worker(self, upload_session_id, schema="public"):
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, get_tenant_model
    from apps.classif_ai.services import StitchImageService

    # Setting the correct schema
    if connection.schema_name != get_public_schema_name():
        connection.set_schema_to_public()

    if schema != get_public_schema_name():
        tenant = get_tenant_model().objects.get(schema_name=schema)
        connection.set_tenant(tenant, include_public=True)

    service = StitchImageService()
    service.stitch(upload_session_id)


def set_schema(schema):
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, get_tenant_model

    if connection.schema_name != get_public_schema_name():
        connection.set_schema_to_public()

    if schema != get_public_schema_name():
        tenant = get_tenant_model().objects.get(schema_name=schema)
        connection.set_tenant(tenant, include_public=True)


# HOW to enforce first parameter needs to be description and second one needs to be input
@shared_task(bind=True)
def copy_images_to_folder(self, input_data, schema="public"):
    set_schema(schema)
    from apps.classif_ai.models import FileSet

    FileSet.objects.copy(input_data)


@before_task_publish.connect
def task_sent_handler(sender=None, headers=None, body=None, **kwargs):
    info = headers if "task" in headers else body
    if not info["ignore_result"]:
        from django.db import transaction
        from django_celery_results.models import TaskResult
        from django_tenants.utils import get_public_schema_name
        import ast

        schema = ast.literal_eval(info.get("kwargsrepr")).get("schema") or get_public_schema_name()
        set_schema(schema)
        with transaction.atomic():
            TaskResult.objects.get_or_create(
                content_type="application/json",
                content_encoding="utf-8",
                task_id=info["id"],
                status=states.PENDING,
                result=None,
                task_name=info["task"],
                task_args=info["argsrepr"],
                task_kwargs=info["kwargsrepr"],
            )
