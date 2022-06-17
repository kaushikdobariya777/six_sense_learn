from apps.classif_ai.tasks import perform_file_set_inference
from django.db import connection, models, transaction
from django.db.models import Q
from django.core.paginator import Paginator

from sixsense.settings import INFERENCE_METHOD


class FileSetInferenceQueueManager(models.Manager):
    def partial_create(self, objs, batch_size=None, ignore_conflicts=False):
        objs_grouped_by_ml_model = {}
        for obj in objs:
            if objs_grouped_by_ml_model.get(obj.ml_model_id, None) is None:
                objs_grouped_by_ml_model[obj.ml_model_id] = []
            objs_grouped_by_ml_model[obj.ml_model_id].append(obj)
        with transaction.atomic():
            for ml_model_id in objs_grouped_by_ml_model:
                file_set_ids = [obj.file_set_id for obj in objs_grouped_by_ml_model[ml_model_id]]
                result = self.filter(~Q(status="FAILED"), file_set_id__in=file_set_ids, ml_model_id=ml_model_id)
                if result:
                    for val in result:
                        file_set_id = val.file_set_id
                        for obj in objs_grouped_by_ml_model[ml_model_id]:
                            if obj.file_set_id == file_set_id:
                                objs_grouped_by_ml_model[ml_model_id].remove(obj)
            objs = []
            for val in objs_grouped_by_ml_model.values():
                objs.extend(val)

            super(FileSetInferenceQueueManager, self).bulk_create(objs, batch_size, ignore_conflicts)
            for obj in objs:
                if INFERENCE_METHOD == "SAGEMAKER_ASYNC":
                    # ToDo: When doing in bulk, this may be very slow and requests may time out
                    from apps.classif_ai.services import InferenceService

                    InferenceService(ml_model_id=obj.ml_model_id, file_set_id=obj.file_set_id).perform()
                else:
                    perform_file_set_inference.delay(
                        file_set_id=obj.file_set_id, ml_model_id=obj.ml_model_id, schema=connection.schema_name
                    )


class FileSetManager(models.Manager):
    def copy(self, input_data):
        from apps.classif_ai.models import FileSet, File
        from apps.classif_ai.filters import FileSetFilterSet

        with transaction.atomic():
            file_set_filter = FileSetFilterSet(input_data.get("file_set_filters"), queryset=FileSet.objects.all())
            skip_existing_images = input_data.get("skip_existing_images", False)
            upload_session_id = input_data.get("upload_session_id")

            file_set_queryset = file_set_filter.qs.prefetch_related("files")

            if skip_existing_images:
                existing_file_names = FileSet.objects.filter(upload_session_id=upload_session_id).values_list(
                    "files__name", flat=True
                )
                file_set_queryset = file_set_queryset.exclude(files__name__in=existing_file_names)
            new_files = []
            paginator = Paginator(file_set_queryset, 10000)
            for page_number in paginator.page_range:
                page = paginator.page(page_number)
                for file_set in page.object_list:
                    old_id = file_set.id
                    file_set.id = None
                    file_set.upload_session_id = upload_session_id
                    file_set.save()
                    for file in File.objects.filter(file_set_id=old_id):
                        file.id = None
                        file.file_set = file_set
                        new_files.append(file)
            File.objects.bulk_create(new_files, ignore_conflicts=True)
