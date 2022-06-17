import json
import os
import sys
from datetime import datetime, timezone
from pydoc import locate
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.db.models.expressions import F

from django.db.models.query import QuerySet

import boto3
import requests
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields.citext import CITextField
from django.db.models import JSONField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.files.storage import get_storage_class, default_storage
from django.db import models, connection, transaction
from django.contrib.gis.db import models
from django.db.models import Func, Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.text import get_valid_filename
from rest_framework import serializers
from django_tenants.utils import schema_context

from apps.classif_ai.helpers import (
    add_uuid_to_file_name,
    calculate_iou,
    generate_code,
    create_celery_format_message,
    prepare_training_session_defects_json,
)
from apps.classif_ai.managers import FileSetInferenceQueueManager, FileSetManager
from apps.classif_ai.tasks import perform_file_set_inference
from apps.subscriptions.models import Subscription
from common.models import Base
from common.services import S3Service
from sixsense import settings
from sixsense.settings import (
    DS_MODEL_INVOCATION_PATH,
    DEFAULT_FILE_STORAGE_OBJECT,
    CUSTOM_MODELS_PATH,
    WAFERMAP_PLOTTING_URL,
    INFERENCE_METHOD,
    RETRAINING_QUEUE,
    RETRAINING_QUEUE_REGION_NAME,
)
from sixsense.settings import AUTH_USER_MODEL as User
from django.utils.translation import ugettext_lazy as _

file_storage = get_storage_class()


class MlModel(Base):

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("training", "Training"),
        ("ready_for_deployment", "Ready for Deployment"),
        ("training_failed", "Training failed"),
        ("deployed_in_prod", "Deployed in production"),
        ("deleted", "Deleted"),
        ("user_terminated", "Terminated by user"),
        ("retired", "Retied after deployment"),
    )

    # max_length is not enforced at a database level.
    name = CITextField(max_length=100, unique=True)
    path = JSONField(default=dict, blank=True)
    input_format = JSONField(default=dict, blank=True)
    output_format = JSONField(default=dict, blank=True)
    code = models.CharField(
        max_length=100,
    )
    version = models.IntegerField()
    status = models.CharField(choices=STATUS_CHOICES, max_length=50)
    is_stable = models.BooleanField(default=False)
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT, related_name="ml_models")
    training_performance_metrics = JSONField(default=dict, blank=True)
    use_case = models.ForeignKey("UseCase", on_delete=models.PROTECT, related_name="ml_models")
    confidence_threshold = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    inference_endpoint = models.CharField(max_length=1024, blank=True)
    inference_endpoint_region = models.CharField(max_length=32, blank=True)
    artifact_path = models.CharField(max_length=1024, blank=True)
    models = {}

    def __str__(self):
        return f"{self.name}-{self.code}-{self.version}"

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            if self.status == "deployed_in_prod":
                already_deployed_models = (
                    MlModel.objects.filter(status="deployed_in_prod", use_case=self.use_case)
                    .exclude(id=self.id)
                    .values("id", "status")
                )
                for deployed_model_id in [item["id"] for item in already_deployed_models]:
                    MlModelDeploymentHistory.objects.filter(ml_model_id=deployed_model_id, ends_at=None).update(
                        ends_at=datetime.now(timezone.utc)
                    )
                already_deployed_models.update(status="retired")
            if self.status == "retired":
                MlModelDeploymentHistory.objects.filter(ml_model=self, ends_at=None).update(
                    ends_at=datetime.now(timezone.utc)
                )
            super(MlModel, self).save(*args, **kwargs)

    def clean(self, *args, **kwargs):
        if self.status == "deployed_in_prod":
            # models = MlModel.objects.filter(use_case=self.use_case, status='deployed_in_prod').exclude(id=self.id)
            # if models:
            #     raise ValidationError({'status': 'One use case can only have one model deployed in production.'})
            if self.id:
                current_model_refreshed_from_db = MlModel.objects.get(pk=self.id)
                if not (
                    current_model_refreshed_from_db.status == "ready_for_deployment"
                    or current_model_refreshed_from_db.status == "deployed_in_prod"
                    or current_model_refreshed_from_db.status == "retired"
                ):
                    raise ValidationError(
                        {"status": "Only models with previous status of ready_for_deployment can be deployed"}
                    )

    @property
    def type(self):
        return self.use_case.type

    @property
    def classification_type(self):
        return self.use_case.classification_type

    @classmethod
    def load_model(cls, model_id):
        try:
            sys.path.append(DS_MODEL_INVOCATION_PATH)
            # sys.path.append(GF_DS_MODEL_INVOCATION_PATH)
            # sys.path.append(STM_DS_MODEL_INVOCATION_PATH)
            # sys.path.append(SKYWORKS_DS_MODEL_INVOCATION_PATH)
            db_model = cls.objects.get(id=model_id)
            model_invocation_path = db_model.path.get("invocation_path", None)
            if model_invocation_path:
                local_path = os.path.join(CUSTOM_MODELS_PATH, model_invocation_path)
                if not os.path.exists(local_path):
                    s3_service = S3Service()
                    files = s3_service.list_objects(model_invocation_path)
                    if files:
                        # os.makedirs(local_path, exist_ok=True)
                        for filee in files:
                            file = filee["Key"]
                            url = s3_service.generate_pre_signed_url(file)
                            r = requests.get(url)
                            # local_path = os.path.dirname(os.path.join('all_models', file))
                            # os.makedirs(local_path, exist_ok=True)
                            os.makedirs(os.path.dirname(os.path.join("all_models", file)), exist_ok=True)
                            with open(os.path.join("all_models", file), "wb") as f:
                                f.write(r.content)
                # from invoke import Defect_detector
                Defect_detector = locate(".".join(os.path.join(local_path, "invoke/Defect_detector").split("/")))
            # elif connection.schema_name == 'gf7':
            #     from gf_deployment.invoke import Defect_detector
            # elif connection.schema_name == 'demo' and db_model.id==8:
            #     from gf_deployment.invoke import Defect_detector
            # elif connection.schema_name == 'stmicro':
            #     from stm_deployment.invoke import Defect_detector
            # elif connection.schema_name == 'skyworks':
            #     from skyworks_deployment.invoke import Defect_detector
            else:
                from invoke import Defect_detector
            if cls.models.get(connection.tenant.schema_name, None) is None:
                cls.models[connection.tenant.schema_name] = {}
            cls.models[connection.tenant.schema_name][model_id] = Defect_detector(db_model.path)
        except cls.DoesNotExist:
            raise
        except RuntimeError as e:
            retry_loading = False
            for schema_name, loaded_models in cls.models:
                for loaded_model_id in loaded_models.keys():
                    with schema_context(schema_name):
                        cou = FileSetInferenceQueue.objects.filter(
                            ml_model_id=loaded_model_id, status__in=["PENDING", "PROCESSING"]
                        ).count()
                        if cou == 0:
                            try:
                                cls.models[schema_name][loaded_model_id].predictor.destroy()
                            except Exception:
                                pass
                            del cls.models[loaded_model_id]
                            retry_loading = True
            if retry_loading:
                return cls.load_model(model_id)
            else:
                raise
        return cls.models[connection.tenant.schema_name][model_id]

    def copy_defects_from(self, ml_model, created_by_id):
        ml_model_defect_sql = """
            insert into classif_ai_mlmodeldefect (created_ts,updated_ts,created_by_id,defect_id,ml_model_id,updated_by_id)
            select now(),now(),{created_by_id},cam.defect_id, {new_ml_model}, {updated_by_id}
            from classif_ai_mlmodeldefect cam
            where ml_model_id={old_ml_model}
        """
        ml_model_defect_sql = ml_model_defect_sql.format(
            new_ml_model=self.id,
            old_ml_model=ml_model.id,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        with connection.cursor() as cursor:
            cursor.execute(ml_model_defect_sql)

    def deploy(self):
        if self.status not in ["retired", "ready_for_deployment"]:
            raise ValidationError(f"Can't deploy status {self.status} ml model in production.")
        self.status = "deployed_in_prod"
        self.save()

    def undeploy(self):
        if "deployed_in_prod" not in self.status:
            raise ValidationError(f"Only deployed ml model can be undeploy.")
        self.status = "retired"
        self.save()

    class Meta:
        unique_together = [["code", "version"]]


class MlModelDeploymentHistory(Base):
    ml_model = models.ForeignKey(
        MlModel, null=False, blank=False, on_delete=models.CASCADE, related_name="deployments"
    )
    starts_at = models.DateTimeField(null=False, blank=False)
    ends_at = models.DateTimeField(null=True, blank=True)


class Defect(Base):
    # max_length is not enforced at a database level.
    name = CITextField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    code = models.SlugField(max_length=100, unique=True, blank=True)
    organization_defect_code = models.CharField(blank=True, max_length=100)
    ml_models = models.ManyToManyField(through="MlModelDefect", to=MlModel, related_name="defects")
    # reference_files = ArrayField(models.CharField(max_length=1024), default=list)
    reference_files = models.ManyToManyField(to="File", related_name="referenced_defects")
    use_cases = models.ManyToManyField(to="UseCase", through="UseCaseDefect", related_name="defects")
    subscription = models.ForeignKey(
        "subscriptions.Subscription", null=False, on_delete=models.PROTECT, related_name="defects"
    )

    def __str__(self):
        return self.name

    # def pre_signed_post_data(self):
    #     s3_service = S3Service()
    #     pre_signed_post_data = {}
    #     for path in self.reference_files:
    #         pre_signed_post_data['path'] = s3_service.generate_pre_signed_post(path)
    #     return pre_signed_post_data

    # def save(self, *args, **kwargs):
    #     # ToDo: How do we manage if the user wants to add a new file?
    #     #  How do we manage if the user deletes an existing file?
    #     #  How do we decide when to prepend the reference files with the prefix.
    #     #  Solution: Create a different table for the reference files or just have a manytomany with the
    #     #  to File table
    #     for i, file in enumerate(self.reference_files):
    #         file = os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, add_uuid_to_file_name(file))
    #         self.reference_files[i] = file
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_code(self.name)
        super().save(*args, **kwargs)


class DefectMetaInfo(Base):
    defect = models.ForeignKey(Defect, on_delete=models.PROTECT, related_name="defect_meta_info")
    meta_info = JSONField(default=dict)
    # reference_files = ArrayField(models.CharField(max_length=1024), default=list)
    reference_files = models.ManyToManyField(to="File")

    # def save(self, *args, **kwargs):
    #     for i, file in enumerate(self.reference_files):
    #         file = os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, add_uuid_to_file_name(file))
    #         self.reference_files[i] = file
    #     super().save(*args, **kwargs)


class UseCase(Base):
    USE_CASE_TYPE_CHOICES = (
        ("DETECTION", "Detection"),
        ("CLASSIFICATION", "Classification"),
        ("CLASSIFICATION_AND_DETECTION", "Detection and Classification"),
    )

    CLASSIFICATION_TYPE_CHOICES = (
        ("SINGLE_LABEL", "Single Label"),
        ("MULTI_LABEL", "Multi Label"),
    )

    # max_length is not enforced at a database level.
    name = CITextField(max_length=100, unique=True)
    type = models.CharField(max_length=64, choices=USE_CASE_TYPE_CHOICES, default="DETECTION")
    classification_type = models.CharField(max_length=64, choices=CLASSIFICATION_TYPE_CHOICES, default="MULTI_LABEL")
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT, related_name="use_cases")
    automation_conditions = JSONField(default=dict, blank=True)  # {'field': 'wafer', 'threshold_percentage': 80}

    def __str__(self):
        return self.name


class UseCaseDefect(Base):
    use_case = models.ForeignKey(UseCase, on_delete=models.PROTECT, related_name="use_case_defects")
    defect = models.ForeignKey(Defect, on_delete=models.PROTECT, related_name="use_case_defects")
    # reference_files = ArrayField(models.CharField(max_length=1024), default=list)
    reference_files = models.ManyToManyField(to="File")

    # def pre_signed_post_data(self):
    #     s3_service = S3Service()
    #     pre_signed_post_data = {}
    #     for path in self.reference_files:
    #         pre_signed_post_data['path'] = s3_service.generate_pre_signed_post(path)
    #     return pre_signed_post_data

    # def save(self, *args, **kwargs):
    #     for i, file in enumerate(self.reference_files):
    #         file = os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, add_uuid_to_file_name(file))
    #         self.reference_files[i] = file
    #     super().save(*args, **kwargs)

    class Meta:
        unique_together = [["use_case", "defect"]]


class MlModelDefect(Base):
    ml_model = models.ForeignKey(MlModel, on_delete=models.PROTECT)
    defect = models.ForeignKey(Defect, on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if (
                UseCaseDefect.objects.filter(use_case_id=self.ml_model.use_case_id, defect_id=self.defect_id).count()
                == 0
            ):
                UseCaseDefect.objects.create(use_case_id=self.ml_model.use_case_id, defect_id=self.defect_id)

    class Meta:
        unique_together = [["ml_model", "defect"]]


class Tag(Base):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True, max_length=1024)


class WaferMap(Base):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("auto_classified", "Auto Classified"),
        ("manual_classification_pending", "Manual classification pending"),
        ("manually_classified", "Manually Classified"),
    )
    organization_wafer_id = models.CharField(max_length=1024, unique=True)
    meta_data = JSONField(default=dict, blank=True)
    status = models.CharField(choices=STATUS_CHOICES, max_length=50, default="pending")
    tags = models.ManyToManyField(through="WaferMapTag", to=Tag, related_name="wafer_maps")
    img_meta_info = JSONField(default=dict, blank=True)
    image_path = models.CharField(max_length=2056, blank=True)
    coordinate_meta_info = JSONField(default=dict, blank=True)
    defect_pattern_info = JSONField(default=dict, blank=True)

    def get_pre_signed_url(self):
        if self.image_path:
            return DEFAULT_FILE_STORAGE_OBJECT.url(self.image_path)
        else:
            return

    def get_scaling_factor(self):
        if "scaling_factor" in self.img_meta_info:
            return self.img_meta_info["scaling_factor"]
        else:
            return []

    def get_cords_center(self):
        if "cords_center" in self.img_meta_info:
            return self.img_meta_info["cords_center"]
        else:
            return []

    @staticmethod
    def create_wafer_image(meta_data, coordinate_meta_info, pre_signed_post_data):
        url = WAFERMAP_PLOTTING_URL
        params = {
            "meta_data": meta_data,
            "pre_signed_post_data": pre_signed_post_data,
            "coordinate_meta_info": coordinate_meta_info,
        }
        if url:
            try:
                r = requests.post(url, data=json.dumps(params), headers={"Content-Type": "application/json"})
                r.raise_for_status()
                response = r.json()
                return response
            except requests.exceptions.RequestException as e:
                raise
        else:
            raise ImproperlyConfigured(
                "WAFERMAP_PLOTTING_URL must be configured in settings for wafermap image generation to work"
            )


class WaferMapTag(models.Model):
    wafer = models.ForeignKey(WaferMap, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT)


class FileSet(Base):
    upload_session = models.ForeignKey(
        "UploadSession", on_delete=models.PROTECT, related_name="file_sets", null=True, blank=True
    )
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT, related_name="file_sets")
    meta_info = JSONField(default=dict, blank=True)
    is_deleted = models.BooleanField(default=False, null=False)
    is_bookmarked = models.BooleanField(default=False, null=False, blank=True)
    use_case = models.ForeignKey("UseCase", on_delete=models.PROTECT, related_name="file_sets", null=True, blank=True)
    wafer = models.ForeignKey(WaferMap, on_delete=models.PROTECT, related_name="file_sets", null=True, blank=True)
    location_on_wafer = models.GeometryField(null=True, blank=True, srid=3857)

    objects = FileSetManager()

    def clean(self, *args, **kwargs):
        if self.subscription_id:
            config = Subscription.objects.get(id=self.subscription_id).file_set_meta_info
            meta_info = self.meta_info

            sub_fields = {}
            for field in config:
                serializer_field = getattr(serializers, field["field_type"])
                sub_fields[field["field"]] = serializer_field(**field["field_props"])

            FileSetMetaInfoSerializer = type("FileSetMetaInfoSerializer", (serializers.Serializer,), sub_fields)
            serializer_data = {}
            for key, val in meta_info.items():
                serializer_data[key] = val
            serializer = FileSetMetaInfoSerializer(data=serializer_data)
            unknown = set(serializer_data) - set(serializer.fields)
            if unknown:
                raise ValidationError("Unknown field(s): {}".format(", ".join(unknown)))
            serializer.is_valid(raise_exception=True)

    def save(self, *args, **kwargs):
        if self.upload_session_id:
            self.use_case_id = self.upload_session.use_case_id
            self.subscription_id = self.upload_session.subscription_id
        else:
            self.use_case_id = None
        self.full_clean()
        if self.wafer and self.meta_info:
            scaling_factor = self.wafer.get_scaling_factor()
            cords_center = self.wafer.get_cords_center()
            region = self.meta_info
            if scaling_factor and cords_center and all(key in region.keys() for key in ["locxum", "locxum"]):
                if cords_center[0] == 0 or cords_center[1] == 0:
                    raise ValidationError("center coordinates should not be zero, normalization will fail")
                region_point = Point(
                    (
                        (cords_center[0] + float(region["locxum"]) * scaling_factor[0]) / (2 * cords_center[0]),
                        (cords_center[1] + float(region["locyum"]) * scaling_factor[1]) / (2 * cords_center[1]),
                    )
                )
                self.location_on_wafer = region_point
        super(FileSet, self).save(*args, **kwargs)

    class Meta:
        indexes = [GinIndex(fields=["meta_info"])]


class File(Base):
    file_set = models.ForeignKey(FileSet, on_delete=models.CASCADE, related_name="files")
    image = models.FileField(storage=file_storage(), null=True, blank=True, max_length=1024)
    name = models.CharField(max_length=1024, blank=True)
    path = models.CharField(max_length=2056, blank=True)

    def __str__(self):
        return f"{self.id}-{self.name}"

    def get_pre_signed_post_data(self):
        s3_service = S3Service()
        return s3_service.generate_pre_signed_post(self.path)

    def get_pre_signed_url(self):
        return DEFAULT_FILE_STORAGE_OBJECT.url(self.path)
        # if settings.TENANT_FILE_STORAGE == "S3":
        #     s3_service = S3Service()
        #     return s3_service.generate_pre_signed_url(self.path)
        # return self.path

    def save(self, *args, **kwargs):
        if self.id is None and self.image:
            if self.name is None:
                self.name = self.image.name
            self.image.name = add_uuid_to_file_name(self.image.name)
        if not self.path:
            if self.image:
                self.path = os.path.join(
                    settings.MEDIA_ROOT, connection.tenant.schema_name, get_valid_filename(self.image.name)
                )
            else:
                self.path = os.path.join(
                    settings.MEDIA_ROOT, connection.tenant.schema_name, add_uuid_to_file_name(self.name)
                )
        super().save(*args, **kwargs)

    # def delete(self, *args, **kwargs):
    # deleted = super().save(*args, **kwargs)
    # def _delete():
    # print("deleting")
    # default_storage.delete(self.path)
    # transaction.on_commit(_delete)
    # return deleted

    class Meta:
        indexes = [
            GinIndex(
                name="file_name_gin_idx",
                fields=["name"],
                opclasses=["gin_trgm_ops"],
            )
        ]


@receiver(post_delete, sender=File)
def file_post_delete(sender, instance, **kwargs):
    if instance.path:

        def _delete():
            default_storage.delete(instance.path)

        transaction.on_commit(_delete)


class UploadSession(Base):
    name = models.CharField(max_length=100, unique=True)
    subscription = models.ForeignKey(
        "subscriptions.Subscription", on_delete=models.PROTECT, related_name="upload_sessions"
    )
    is_live = models.BooleanField(null=False, blank=True, default=False)
    use_case = models.ForeignKey(
        UseCase, null=True, blank=True, on_delete=models.PROTECT, related_name="upload_sessions"
    )
    is_bookmarked = models.BooleanField(default=False, null=False, blank=True)

    def __str__(self):
        return f"{self.id}-{self.name}"

    def save(self, *args, **kwargs):
        if self.use_case_id is None:
            raise ValidationError({"use_case": f"Use case is mandatory field now"})
        super(UploadSession, self).save(*args, **kwargs)


class FileRegion(Base):
    IOU_THRESHOLD_FOR_DETECTION_CORRECTNESS = 0.4
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="file_regions")
    ml_model = models.ForeignKey(MlModel, on_delete=models.PROTECT, related_name="file_regions")
    # defects : {"<defect_id-1>": {confidence: 0.8}, "<defect_id-2>": {confidence: 0.6} }
    defects = JSONField(default=dict)
    # region: {"type": "box", "coordinates": {x:0.2, y: 0.3, h: 0.1, w: 0.2}}
    region = JSONField(default=dict)
    ai_region = models.ForeignKey(
        "FileRegion", on_delete=models.PROTECT, null=True, blank=True, related_name="file_regions"
    )
    is_user_feedback = models.BooleanField(default=False, db_index=True)
    # If correctness is marked as null, user feedback is not given
    # If correctness is marked as 1, it's correct
    # If correctness is marked as -1, it's incorrect
    classification_correctness = models.BooleanField(null=True, blank=True, db_index=True)
    detection_correctness = models.BooleanField(null=True, blank=True, db_index=True)
    is_removed = models.BooleanField(null=False, blank=True, default=False, db_index=True)
    model_output_meta_info = JSONField(default=dict, blank=True)

    class Meta:
        indexes = [GinIndex(fields=["defects"])]

    def is_detected_gte_gt(self):
        if self.ai_region:
            gt_area = self.region["coordinates"]["h"] * self.region["coordinates"]["w"]
            detected_area = self.ai_region.region["coordinates"]["h"] * self.ai_region.region["coordinates"]["w"]
            if detected_area > gt_area:
                return True
            else:
                return False

    def is_gt_region(self):
        if (self.is_user_feedback is True and self.is_removed is False) or (
            (self.classification_correctness is True or self.detection_correctness is True)
            and self.file_regions.count() == 0
        ):
            return True
        return False

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new_record = False
            if self.id is None:
                is_new_record = True
            if self.is_user_feedback and is_new_record and self.ml_model.type == "CLASSIFICATION":
                # ai region marked incorrect or with no feedback but might actually be correct.
                possibly_correct_ai_regions = FileRegion.objects.filter(
                    file_id=self.file_id, ml_model_id=self.ml_model_id, is_user_feedback=False
                )
                for possibly_correct_ai_region in possibly_correct_ai_regions:
                    # if user feedback region matches with the ai region we mark the ai region
                    # correct and get out without saving the user feedback region to the db.
                    if int(list(possibly_correct_ai_region.defects.keys())[0]) == int(list(self.defects.keys())[0]):
                        possibly_correct_ai_region.classification_correctness = True
                        possibly_correct_ai_region.is_removed = False
                        possibly_correct_ai_region.save()
                        return
            super(FileRegion, self).save()
            if not self.is_user_feedback and is_new_record:
                already_existing_feedbacks = FileRegion.objects.filter(
                    ml_model_id=self.ml_model_id,
                    file_id=self.file_id,
                    is_user_feedback=True,
                    ai_region_id__isnull=True,
                    is_removed=False,
                )
                if self.ml_model.type == "CLASSIFICATION":
                    for feedback in already_existing_feedbacks:
                        if list(feedback.defects.keys())[0] == list(self.defects.keys())[0]:
                            feedback.ai_region = self
                            feedback.save()
                            self.classification_correctness = True
                        else:
                            self.classification_correctness = False
                    self.save()
                else:
                    matching_region = None
                    for feedback in already_existing_feedbacks:
                        iou = calculate_iou(
                            [
                                feedback.region["coordinates"]["x"],
                                feedback.region["coordinates"]["y"],
                                feedback.region["coordinates"]["x"] + feedback.region["coordinates"]["w"],
                                feedback.region["coordinates"]["y"] + feedback.region["coordinates"]["h"],
                            ],
                            [
                                self.region["coordinates"]["x"],
                                self.region["coordinates"]["y"],
                                self.region["coordinates"]["x"] + self.region["coordinates"]["w"],
                                self.region["coordinates"]["y"] + self.region["coordinates"]["h"],
                            ],
                        )
                        if iou > 0.4:
                            if matching_region:
                                if matching_region[1] < iou:
                                    matching_region = [feedback, iou]
                            else:
                                matching_region = [feedback, iou]
                    if matching_region:
                        matching_region[0].ai_region = self
                        matching_region[0].save()
            if self.ai_region:
                model_type = self.ml_model.type
                region = self.region
                ai_region = self.ai_region
                if model_type == "DETECTION" or model_type == "CLASSIFICATION_AND_DETECTION":
                    iou = calculate_iou(
                        boxA=[
                            region["coordinates"]["x"],
                            region["coordinates"]["y"],
                            region["coordinates"]["x"] + region["coordinates"]["w"],
                            region["coordinates"]["y"] + region["coordinates"]["h"],
                        ],
                        boxB=[
                            ai_region.region["coordinates"]["x"],
                            ai_region.region["coordinates"]["y"],
                            ai_region.region["coordinates"]["x"] + ai_region.region["coordinates"]["w"],
                            ai_region.region["coordinates"]["y"] + ai_region.region["coordinates"]["h"],
                        ],
                    )
                    self.detection_correctness = True
                    if iou > 0.4:
                        ai_region.detection_correctness = True
                    else:
                        ai_region.detection_correctness = False
                if model_type == "CLASSIFICATION_AND_DETECTION":
                    if sorted(self.defects) == sorted(self.ai_region.defects):
                        ai_region.classification_correctness = True
                    else:
                        ai_region.classification_correctness = False
                ai_region.save()

            FileRegionHistory.objects.create(
                file_id=self.file_id,
                ml_model_id=self.ml_model_id,
                defects=self.defects,
                region=self.region,
                ai_region_id=self.ai_region_id,
                file_region_id=self.id,
                is_user_feedback=self.is_user_feedback,
            )


class FileRegionHistory(Base):
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="file_region_history")
    ml_model = models.ForeignKey(MlModel, on_delete=models.PROTECT, related_name="file_region_history")
    defects = JSONField(default=dict)
    region = JSONField(default=dict)
    ai_region = models.ForeignKey(
        "FileRegion", on_delete=models.PROTECT, null=True, related_name="ai_file_region_history"
    )
    file_region = models.ForeignKey("FileRegion", on_delete=models.CASCADE, related_name="file_region_history")
    is_user_feedback = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)


class FileSetInferenceQueue(Base):

    STATUS_CHOICES = (
        ("PENDING", "PENDING"),
        ("PROCESSING", "PROCESSING"),
        ("FINISHED", "FINISHED"),
        ("FAILED", "FAILED"),
    )

    file_set = models.ForeignKey(FileSet, on_delete=models.CASCADE, related_name="file_set_inference_queues")
    ml_model = models.ForeignKey(MlModel, on_delete=models.PROTECT, related_name="file_set_inference_queues")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="PENDING")
    inference_id = models.CharField(max_length=64, blank=True)

    objects = FileSetInferenceQueueManager()

    def clean(self, *args, **kwargs):
        if (
            self.id is None
            and FileSetInferenceQueue.objects.filter(
                ~Q(status="FAILED"), ml_model=self.ml_model, file_set=self.file_set
            ).exists()
        ):
            raise ValidationError("A FileSetInferenceQueue object with this ml_model and file_set already exists")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.full_clean()
            perform_inference = False
            if self.id is None:
                perform_inference = True
            super(FileSetInferenceQueue, self).save(*args, **kwargs)
            if perform_inference:
                if INFERENCE_METHOD == "SAGEMAKER_ASYNC":
                    from apps.classif_ai.services import InferenceService

                    InferenceService(ml_model_id=self.ml_model_id, file_set_id=self.file_set_id).perform()
                else:
                    perform_file_set_inference.delay(
                        file_set_id=self.file_set_id, ml_model_id=self.ml_model_id, schema=connection.schema_name
                    )


class TrainingSession(Base):
    old_ml_model = models.ForeignKey(MlModel, on_delete=models.PROTECT, null=True, blank=True)
    new_ml_model = models.OneToOneField(
        MlModel, on_delete=models.PROTECT, related_name="training_session", unique=True
    )
    file_sets = models.ManyToManyField(FileSet, through="TrainingSessionFileSet")
    status = JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def start(self):
        if self.new_ml_model.status != "draft":
            raise ValidationError("Training cannot be started as it's not a draft")
        with transaction.atomic():
            body = {"training_session_id": self.id, "schema": connection.tenant.schema_name}
            message = create_celery_format_message("retrain.run_training", args=[json.dumps(body)])
            client = boto3.client("sqs", region_name=RETRAINING_QUEUE_REGION_NAME)
            try:
                resp = client.send_message(
                    QueueUrl=RETRAINING_QUEUE,
                    MessageBody=message,
                )
                MlModel.objects.filter(id=self.new_ml_model_id).update(status="training")
            except (client.exceptions.InvalidMessageContents, client.exceptions.UnsupportedOperation) as e:
                # Should we update training failed or should we keep it in draft status only to let users retry?
                raise

    def copy_gt_defects(self, file_sets=None):
        query = Q()
        if file_sets is not None:
            query = Q(file_set__in=file_sets)
        training_session_file_sets = TrainingSessionFileSet.objects.filter(Q(training_session=self) & query)

        use_case_type = self.new_ml_model.use_case.type
        if use_case_type == "CLASSIFICATION":
            training_session_file_sets = (
                training_session_file_sets.annotate(train=F("id"), file_id=F("file_set__files"))
                .values(
                    "train",
                    "file_set_id",
                    "file_set__use_case__type",
                    "file_id",
                    "file_set__files__gt_classifications__is_no_defect",
                )
                .annotate(
                    gt_defect=ArrayAgg(
                        "file_set__files__gt_classifications__gt_classification_annotations__defect",
                        filter=Q(
                            file_set__files__gt_classifications__gt_classification_annotations__defect__isnull=False
                        ),
                    )
                )
            )

            training_session_sql = """
                update classif_ai_trainingsessionfileset
                set defects = temp.d
                from  (
                select train, json_build_object('id', file_set_id, 'files', array_to_json(array_agg(json_build_object('id',file_id,'gt_classification', json_build_object('is_no_defect',is_no_defect,'defects',array_to_json(gt_defect )))) )) as d
                    from
                    (
                    {sql}
                    ) x
                    group by train, file_set_id
                ) temp
                WHERE temp.train = classif_ai_trainingsessionfileset.id
            """
            training_session_sql = training_session_sql.format(sql=training_session_file_sets.query)
            with connection.cursor() as cursor:
                cursor.execute(training_session_sql)
        else:
            # TODO: above setup for classification needs to be done for detection too
            for training_session_file_set in training_session_file_sets:
                file_set = training_session_file_set.file_set
                gt_defects = prepare_training_session_defects_json(file_set, use_case_type)
                training_session_file_set.defects = gt_defects
                training_session_file_set.save()

    def copy_files_from_model(self, old_ml_model, created_by_id):
        training_session_sql = """
            insert into classif_ai_trainingsessionfileset (created_ts,updated_ts,defects,created_by_id,file_set_id,training_session_id,updated_by_id,belongs_to_old_model_training_data,dataset_train_type)
            select now(),now(),tsf.defects,{created_by_id},tsf.file_set_id,{training_session},{updated_by_id},tsf.belongs_to_old_model_training_data,tsf.dataset_train_type
            from classif_ai_trainingsessionfileset tsf 
            inner join classif_ai_trainingsession ts
                on tsf.training_session_id = ts.id
            where ts.new_ml_model_id = {old_ml_model}
        """
        training_session_sql = training_session_sql.format(
            training_session=self.id,
            old_ml_model=old_ml_model.id,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        with connection.cursor() as cursor:
            cursor.execute(training_session_sql)

    def copy_files_from_fileset_qs(self, file_set_query_set: QuerySet, created_by_id):
        file_set_sql = file_set_query_set.values("id").query
        training_session_sql = """
            insert into classif_ai_trainingsessionfileset (created_ts,updated_ts,defects,created_by_id,file_set_id,training_session_id,updated_by_id,belongs_to_old_model_training_data,dataset_train_type)
            select now(),now(),'{defects}',{created_by_id},temp.id,{training_session},{updated_by_id},false,''
            from ({file_set_sql}) temp
        """
        training_session_sql = training_session_sql.format(
            defects="{}",
            training_session=self.id,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
            file_set_sql=file_set_sql,
        )
        with connection.cursor() as cursor:
            cursor.execute(training_session_sql)


# ToDo: Rename this to TrainingData
class TrainingSessionFileSet(Base):
    DATASET_CATEGORY_CHOICES = (("TEST", "Test"), ("TRAIN", "Train"), ("VALIDATION", "Validation"))
    file_set = models.ForeignKey(FileSet, on_delete=models.PROTECT)
    training_session = models.ForeignKey(TrainingSession, on_delete=models.PROTECT)
    """
    Structure of the defects JSON will be like below
    {
        <file_id>: [<FileRegion>, <FileRegion>]
    }
    """
    defects = JSONField(default=dict)
    dataset_train_type = models.CharField(choices=DATASET_CATEGORY_CHOICES, max_length=50, blank=True)
    belongs_to_old_model_training_data = models.BooleanField(null=False, default=False)

    # TODO Need to validate classification and detection defects
    def clean(self, *args, **kwargs):
        if self.file_set_id:
            files = File.objects.filter(file_set=self.file_set).values_list("id", flat=True)
            for key, val in self.defects.items():
                if key == "files":
                    for file in val:
                        for k, v in file.items():
                            if k == "id" and int(v) not in files:
                                raise ValidationError(
                                    {"defects": f"File id {v} is invalid for fileset id {self.file_set_id}"}
                                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super(TrainingSessionFileSet, self).save(*args, **kwargs)


class JsonKeys(Func):
    function = "jsonb_object_keys"


class UserClassification(models.Model):
    file = models.ForeignKey(File, related_name="user_classifications", on_delete=models.CASCADE)
    is_no_defect = models.BooleanField(null=False, default=False)
    created_ts = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_ts = models.DateTimeField(_("Last Updated Date"), auto_now=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    defects = models.ManyToManyField(
        through="UserClassificationDefect", to=Defect, related_name="user_classifications"
    )
    # ToDo: Add a validation to check use case type before creating the record.
    #  A file belonging to detection use case should have ZERO records in this table

    class Meta:
        unique_together = [["file", "user"]]

    def save(self, *args, **kwargs):
        use_case_type = UseCase.objects.get(file_sets__files__id=self.file.id).type
        if use_case_type != "CLASSIFICATION":
            raise ValidationError(f"Can't create user classification for a '{use_case_type}' use case type.")
        super(UserClassification, self).save(*args, **kwargs)

    def copy_to_gt(self):
        if self._state.adding:
            raise ValidationError("Can't copy to gt before the user annotation is saved")
        with transaction.atomic():
            gt_classification = GTClassification.objects.filter(file_id=self.file_id).first()
            if not gt_classification:
                gt_classification = GTClassification(file_id=self.file_id, is_no_defect=self.is_no_defect)
            user_classification_defects = UserClassificationDefect.objects.filter(classification=self)
            is_no_defect = False
            if not user_classification_defects:
                is_no_defect = True
            gt_classification.is_no_defect = is_no_defect
            gt_classification.save()
            GTClassificationDefect.objects.filter(classification=gt_classification).delete()
            if gt_classification.is_no_defect is False:
                user_classification_defects = UserClassificationDefect.objects.filter(classification=self)
                gt_classification_defects = []
                for user_classification_defect in user_classification_defects:
                    gt_classification_defects.append(
                        GTClassificationDefect(
                            classification=gt_classification, defect_id=user_classification_defect.defect_id
                        )
                    )
                GTClassificationDefect.objects.bulk_create(gt_classification_defects)


class UserClassificationDefect(Base):
    classification = models.ForeignKey(
        UserClassification, related_name="user_classification_annotations", on_delete=models.CASCADE
    )
    defect = models.ForeignKey(Defect, related_name="user_classification_defects", on_delete=models.PROTECT)
    # ToDo: There should be a validation to validate if the defect being inserted actually belongs to the
    #  use case of the file or not

    class Meta:
        unique_together = [["classification", "defect"]]


class UserDetection(models.Model):
    file = models.ForeignKey(File, related_name="user_detections", on_delete=models.CASCADE)
    is_no_defect = models.BooleanField(null=False, default=False)
    created_ts = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_ts = models.DateTimeField(_("Last Updated Date"), auto_now=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        unique_together = [["file", "user"]]

    def save(self, *args, **kwargs):
        use_case_type = UseCase.objects.get(file_sets__files__id=self.file.id).type
        if use_case_type != "CLASSIFICATION_AND_DETECTION":
            raise ValidationError(f"Can't create user detection for a '{use_case_type}' use case type.")
        super(UserDetection, self).save(*args, **kwargs)

    def copy_to_gt(self):
        if self._state.adding:
            raise ValidationError("Can't copy to gt before the user annotation is saved")
        with transaction.atomic():
            gt_detection = GTDetection.objects.filter(file_id=self.file_id).first()
            if not gt_detection:
                gt_detection = GTDetection(file_id=self.file_id, is_no_defect=self.is_no_defect)
            gt_detection.is_no_defect = self.is_no_defect
            gt_detection.save()
            GTDetectionRegion.objects.filter(detection=gt_detection).delete()
            if gt_detection.is_no_defect is False:
                user_detection_regions = UserDetectionRegion.objects.filter(detection=self)
                for user_detection_region in user_detection_regions:
                    gt_detection_region = GTDetectionRegion.objects.create(
                        detection=gt_detection, region=user_detection_region.region
                    )
                    user_detection_region_defects = UserDetectionRegionDefect.objects.filter(
                        detection_region=user_detection_region
                    )
                    gt_detection_region_defects = []
                    for user_detection_region_defect in user_detection_region_defects:
                        gt_detection_region_defects.append(
                            GTDetectionRegionDefect(
                                detection_region=gt_detection_region, defect_id=user_detection_region_defect.defect_id
                            )
                        )
                    GTDetectionRegionDefect.objects.bulk_create(gt_detection_region_defects)


class UserDetectionRegion(Base):
    detection = models.ForeignKey(UserDetection, related_name="detection_regions", on_delete=models.CASCADE)
    region = models.GeometryField(null=False, srid=3857)
    defects = models.ManyToManyField(
        through="UserDetectionRegionDefect", to=Defect, related_name="user_detection_regions"
    )

    class Meta:
        unique_together = [["detection", "region"]]


class UserDetectionRegionDefect(Base):
    detection_region = models.ForeignKey(
        UserDetectionRegion, related_name="user_detection_region_annotations", on_delete=models.CASCADE
    )
    defect = models.ForeignKey(Defect, related_name="user_detection_region_defects", on_delete=models.PROTECT)
    # ToDo: There should be a validation to validate if the defect being inserted actually belongs to the
    #  use case of the file or not

    class Meta:
        unique_together = [["detection_region", "defect"]]


class GTClassification(Base):
    file = models.OneToOneField(File, related_name="gt_classifications", on_delete=models.CASCADE)
    is_no_defect = models.BooleanField(null=False, default=False)
    defects = models.ManyToManyField(through="GTClassificationDefect", to=Defect, related_name="gt_classifications")


class GTClassificationDefect(Base):
    classification = models.ForeignKey(
        GTClassification, related_name="gt_classification_annotations", on_delete=models.CASCADE
    )
    defect = models.ForeignKey(Defect, related_name="gt_classification_defects", on_delete=models.PROTECT)
    # ToDo: There should be a validation to validate if the defect being inserted actually belongs to the
    #  use case of the file or not

    class Meta:
        unique_together = [["classification", "defect"]]


class GTDetection(Base):
    file = models.OneToOneField(File, related_name="gt_detections", on_delete=models.CASCADE)
    is_no_defect = models.BooleanField(null=False, default=False)


class GTDetectionRegion(Base):
    detection = models.ForeignKey(GTDetection, related_name="detection_regions", on_delete=models.CASCADE)
    region = models.GeometryField(null=False, srid=3857)

    class Meta:
        unique_together = [["detection", "region"]]


class GTDetectionRegionDefect(Base):
    detection_region = models.ForeignKey(
        GTDetectionRegion, related_name="gt_detection_region_annotation", on_delete=models.CASCADE
    )
    defect = models.ForeignKey(Defect, related_name="gt_detection_region_defects", on_delete=models.CASCADE)
    # ToDo: There should be a validation to validate if the defect being inserted actually belongs to the
    #  use case of the file or not

    class Meta:
        unique_together = [["detection_region", "defect"]]


class ModelClassification(Base):
    file = models.ForeignKey(File, related_name="model_classifications", on_delete=models.CASCADE)
    ml_model = models.ForeignKey(MlModel, related_name="model_classification_models", on_delete=models.PROTECT)
    is_no_defect = models.BooleanField(null=False, default=False)
    defects = models.ManyToManyField(
        through="ModelClassificationDefect", to=Defect, related_name="model_classifications"
    )

    class Meta:
        unique_together = [["file", "ml_model"]]


class ModelClassificationDefect(Base):
    classification = models.ForeignKey(
        ModelClassification, related_name="model_classification_annotations", on_delete=models.CASCADE
    )
    defect = models.ForeignKey(Defect, related_name="model_classification_defects", on_delete=models.PROTECT)
    confidence = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    # ToDo: There should be a validation to validate if the defect being inserted actually belongs to the
    #  use case of the file or not

    class Meta:
        unique_together = [["classification", "defect"]]


class ModelDetection(Base):
    file = models.ForeignKey(File, related_name="model_detections", on_delete=models.CASCADE)
    ml_model = models.ForeignKey(MlModel, related_name="model_detection_models", on_delete=models.PROTECT)
    is_no_defect = models.BooleanField(null=False, default=False)

    class Meta:
        unique_together = [["file", "ml_model"]]


class ModelDetectionRegion(Base):
    detection = models.ForeignKey(ModelDetection, related_name="detection_regions", on_delete=models.CASCADE)
    region = models.GeometryField(null=False, srid=3857)
    defects = models.ManyToManyField(
        through="ModelDetectionRegionDefect", to=Defect, related_name="model_detection_regions"
    )
    model_output_meta_info = JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [["detection", "region"]]


class ModelDetectionRegionDefect(models.Model):
    detection_region = models.ForeignKey(ModelDetectionRegion, related_name="region_defects", on_delete=models.CASCADE)
    defect = models.ForeignKey(Defect, related_name="model_detection_region_defects", on_delete=models.PROTECT)
    confidence = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    # ToDo: There should be a validation to validate if the defect being inserted actually belongs to the
    #  use case of the file or not

    class Meta:
        unique_together = [["detection_region", "defect"]]
