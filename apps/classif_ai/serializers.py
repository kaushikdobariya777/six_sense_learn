import importlib
import os
import uuid
import ast

from django.contrib.gis.geos import Polygon
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import default_storage
from django.db import transaction, connection
from django.db.models.aggregates import Max
from django.db.models.expressions import F
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from sixsense.settings import IMAGE_HANDLER_QUEUE_URL

from apps.classif_ai.helpers import (
    add_uuid_to_file_name,
    inference_output_queue,
)
from apps.classif_ai.models import (
    FileSet,
    File,
    ModelClassification,
    ModelDetection,
    ModelDetectionRegion,
    TrainingSession,
    TrainingSessionFileSet,
    UploadSession,
    MlModel,
    FileRegion,
    FileRegionHistory,
    Defect,
    FileSetInferenceQueue,
    UseCase,
    UseCaseDefect,
    MlModelDefect,
    DefectMetaInfo,
    UserClassification,
    UserClassificationDefect,
    UserDetection,
    UserDetectionRegionDefect,
    UserDetectionRegion,
    WaferMap,
    Tag,
)
from apps.subscriptions.models import Subscription
from apps.users.serializers import UserSerializer
from common.services import S3Service
from sixsense import settings

from django_celery_results.models import TaskResult


class FileCreateSerializer(serializers.ModelSerializer):
    pre_signed_post_data = serializers.SerializerMethodField(read_only=True)
    url = serializers.SerializerMethodField(read_only=True)

    def get_pre_signed_post_data(self, instance):
        return instance.get_pre_signed_post_data()

    def get_url(self, instance):
        return instance.get_pre_signed_url()

        # TODO: detection code needs to be corrected, some issue with gt models
        # gt_detection_region_annotation is not found in instance.gt_detections.detection_regions.gt_detection_region_annotation

        # try:
        #     gtdetectregion_defect = {str(defect_name) for defect_name in instance.gt_detections.detection_regions.gt_detection_region_annotation.defect.all()}
        # except AttributeError as e:
        #     if str(e) != 'File has no gt_detections.':
        #         import code
        #         code.interact(local=dict(locals(),**globals()))
        #         # raise
        #     gtdetectregion_defect = set()
        # return gtclassif_defect | gtdetectregion_defect

    class Meta:
        model = File
        fields = ["id", "file_set", "name", "path", "image", "pre_signed_post_data", "url"]
        read_only_fields = ["file_set"]


class FileReadSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)

    def get_url(self, instance):
        return instance.get_pre_signed_url()

    class Meta:
        model = File
        fields = ["id", "file_set", "name", "url"]
        read_only_fields = ["file_set", "name"]


class FileSetCreateSerializer(serializers.ModelSerializer):
    files = FileCreateSerializer(many=True, required=False)
    user_name = serializers.SerializerMethodField(read_only=True)
    upload_session_name = serializers.SerializerMethodField(read_only=True)
    location_on_wafer = serializers.SerializerMethodField(read_only=True)

    def get_user_name(self, obj):
        try:
            return obj.created_by.display_name
        except:
            return None

    def get_upload_session_name(self, obj):
        try:
            return obj.upload_session.name
        except:
            return ""

    def get_location_on_wafer(self, instance):
        if instance.location_on_wafer:
            coords = instance.location_on_wafer.coords
            return {
                "type": "point",
                "coordinates": {
                    "x": coords[0],
                    "y": coords[1],
                },
            }

    class Meta:
        model = FileSet
        fields = [
            "id",
            "files",
            "upload_session",
            "subscription",
            "meta_info",
            "created_ts",
            "updated_ts",
            "created_by",
            "upload_session_name",
            "user_name",
            "is_deleted",
            "is_bookmarked",
            "use_case",
            "wafer",
            "location_on_wafer",
        ]
        read_only_fields = ["created_ts", "created_by", "updated_ts", "is_deleted"]

    def validate(self, data):
        if self.context.get("request", None):
            images = self.context["request"].FILES
            if images:
                files_data = []
                for image in images.getlist("files"):
                    files_data.append({"image": image, "name": image.name})
                data["files"] = files_data
        if self.context["request"].data.get("is_live", None) is True:
            if self.context["request"].data.get("use_case", None) is not None:
                use_case = self.context["request"].data.get("use_case", None)
            else:
                helpers_module = importlib.import_module("apps.classif_ai.helpers")
                use_case = getattr(helpers_module, connection.tenant.schema_name + "_get_use_case_id")(data)
            try:
                data["upload_session_id"] = UploadSession.objects.get(is_live=True, use_case=use_case).id
            except UploadSession.DoesNotExist:
                raise ValidationError("No live upload session exist for the given file")
        if not self.instance or "meta_info" in data:
            if data.get("subscription", None):
                subscription_id = data["subscription"].id
            else:
                subscription_id = self.instance.subscription_id
            config = Subscription.objects.get(id=subscription_id).file_set_meta_info
            helpers_module = importlib.import_module("apps.classif_ai.helpers")
            try:
                data = getattr(helpers_module, connection.tenant.schema_name + "_populate_meta_info")(data)
            except AttributeError:
                pass
            meta_info = data.get("meta_info", {})
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
            if not serializer.is_valid():
                raise ValidationError(serializer.errors)
        return data

    def create(self, validated_data):
        with transaction.atomic():
            helpers_module = importlib.import_module("apps.classif_ai.helpers")
            try:
                validated_data = getattr(helpers_module, connection.tenant.schema_name + "_populate_meta_info")(
                    validated_data
                )
            except AttributeError:
                pass
            try:
                files_data = validated_data.pop("files")
            except KeyError:
                files_data = []
            file_set = FileSet.objects.create(**validated_data)  # Create File Set
            for file_data in files_data:
                file_create_serializer = FileCreateSerializer(data=file_data)
                if file_create_serializer.is_valid(raise_exception=True):
                    file_create_serializer.save(file_set=file_set)  # Create File
            return file_set


class UploadSessionSerializer(serializers.ModelSerializer):
    file_sets = serializers.SerializerMethodField(read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)

    def get_file_sets(self, instance):
        return instance.file_sets.all().count()

    def get_user_name(self, instance):
        try:
            return instance.created_by.display_name
        except:
            return None

    class Meta:
        model = UploadSession
        fields = [
            "id",
            "name",
            "subscription",
            "created_by",
            "created_ts",
            "updated_ts",
            "file_sets",
            "user_name",
            "is_live",
            "use_case",
            "is_bookmarked",
        ]
        read_only_fields = ["created_by", "created_ts", "updated_ts"]


class UseCaseDefectSerializer(serializers.ModelSerializer):
    reference_files = FileReadSerializer(many=True, read_only=True)

    # pre_signed_post_data = serializers.SerializerMethodField(read_only=True)
    # reference_files_urls = serializers.SerializerMethodField(read_only=True)

    # def get_pre_signed_post_data(self, obj):
    #     if self.context.get('request', None):
    #         reference_files = self.context['request'].data.get("reference_files", None)
    #         if reference_files:
    #             s3_service = S3Service()
    #             pre_signed_post_data = {}
    #             for path in reference_files:
    #                 s3_path = os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, path)
    #                 pre_signed_post_data[path] = s3_service.generate_pre_signed_post(s3_path)
    #             return pre_signed_post_data
    #
    # def get_reference_files_urls(self, instance):
    #     urls = []
    #     for ref_file in instance.reference_files:
    #         urls.append(DEFAULT_FILE_STORAGE_OBJECT.url(ref_file))
    #     return urls

    class Meta:
        model = UseCaseDefect
        fields = ["id", "use_case", "defect", "reference_files"]

    def create(self, validated_data):
        with transaction.atomic():
            use_case_defect = UseCaseDefect.objects.create(**validated_data)
            if self.context.get("request", None):
                file_ids = self.context["request"].data.get("reference_file_ids")
                if file_ids:
                    use_case_defect.reference_files.add(*file_ids)
            return use_case_defect


class DefectMetaInfoSerializer(serializers.ModelSerializer):
    reference_files = FileReadSerializer(many=True, read_only=True)

    # pre_signed_post_data = serializers.SerializerMethodField(read_only=True)
    # reference_files_urls = serializers.SerializerMethodField(read_only=True)

    # def get_pre_signed_post_data(self, obj):
    #     if self.context.get('request', None):
    #         reference_files = self.context['request'].data.get("reference_files", None)
    #         if reference_files:
    #             s3_service = S3Service()
    #             pre_signed_post_data = {}
    #             for path in reference_files:
    #                 s3_path = os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, path)
    #                 pre_signed_post_data[path] = s3_service.generate_pre_signed_post(s3_path)
    #             return pre_signed_post_data
    #
    # def get_reference_files_urls(self, instance):
    #     urls = []
    #     for ref_file in instance.reference_files:
    #         urls.append(DEFAULT_FILE_STORAGE_OBJECT.url(ref_file))
    #     return urls

    class Meta:
        model = DefectMetaInfo
        fields = ["id", "defect", "meta_info", "reference_files"]

    def create(self, validated_data):
        with transaction.atomic():
            defect_meta_info = DefectMetaInfo.objects.create(**validated_data)
            if self.context.get("request", None):
                file_ids = self.context["request"].data.get("reference_file_ids")
                if file_ids:
                    defect_meta_info.reference_files.add(*file_ids)
            return defect_meta_info

    def update(self, instance, validated_data):
        with transaction.atomic():
            super(DefectMetaInfoSerializer, self).update(instance, validated_data)
            if self.context.get("request", None):
                file_ids = self.context["request"].data.get("reference_file_ids")
                if file_ids:
                    instance.reference_files.set(file_ids)
            return instance


class DefectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Defect
        fields = [
            "id",
            "name",
            "description",
            "organization_defect_code",
            "code",
            "subscription",
            "created_ts",
            "created_by",
        ]


class DefectDetailedSerializer(serializers.ModelSerializer):
    use_case_defects = UseCaseDefectSerializer(many=True, read_only=True)
    defect_meta_info = DefectMetaInfoSerializer(many=True, read_only=True)
    use_cases = serializers.SerializerMethodField(read_only=True)
    # pre_signed_post_data = serializers.SerializerMethodField(read_only=True)
    # reference_files_urls = serializers.SerializerMethodField(read_only=True)
    reference_files = FileReadSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)

    def get_use_cases(self, obj):
        resp = []
        for usecase in obj.use_cases.all():
            resp.append({"name": usecase.name, "id": usecase.id})
        return resp

    # def get_pre_signed_post_data(self, obj):
    #     if self.context.get('request', None):
    #         reference_files = self.context['request'].data.get("reference_files", None)
    #         if reference_files:
    #             s3_service = S3Service()
    #             pre_signed_post_data = {}
    #             for path in reference_files:
    #                 s3_path = os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, path)
    #                 pre_signed_post_data[path] = s3_service.generate_pre_signed_post(s3_path)
    #             return pre_signed_post_data

    # def get_reference_files_urls(self, instance):
    #     urls = []
    #     for ref_file in instance.reference_files:
    #         urls.append(DEFAULT_FILE_STORAGE_OBJECT.url(ref_file))
    #     return urls

    class Meta:
        model = Defect
        fields = [
            "id",
            "name",
            "description",
            "organization_defect_code",
            "reference_files",
            "defect_meta_info",
            "ml_models",
            "use_cases",
            "use_case_defects",
            "code",
            "subscription",
            "created_ts",
            "created_by",
        ]

    def create(self, validated_data):
        with transaction.atomic():
            defect = Defect.objects.create(**validated_data)
            if self.context.get("request", None):
                file_ids = self.context["request"].data.get("reference_file_ids")
                if file_ids:
                    defect.reference_files.add(*file_ids)
                use_cases = self.context["request"].data.get("use_cases", None)
                if use_cases:
                    UseCaseDefect.objects.filter(defect=defect).delete()
                    use_case_defects = [UseCaseDefect(use_case_id=use_case, defect=defect) for use_case in use_cases]
                    UseCaseDefect.objects.bulk_create(use_case_defects)
                # ml_models = self.context['request'].data.get("ml_models", None)
                # if ml_models:
                #     ml_models_defects = [MlModelDefect(ml_model_id=ml_model, defect=defect) for ml_model in ml_models]
                #     MlModelDefect.objects.bulk_create(ml_models_defects)
            return defect

    def update(self, instance, validated_data):
        with transaction.atomic():
            super(DefectDetailedSerializer, self).update(instance, validated_data)
            use_cases = self.context["request"].data.get("use_cases", None)
            if use_cases is not None:
                UseCaseDefect.objects.filter(defect=instance).delete()
                use_case_defects = [UseCaseDefect(use_case_id=use_case, defect=instance) for use_case in use_cases]
                UseCaseDefect.objects.bulk_create(use_case_defects)
            if self.context.get("request", None):
                file_ids = self.context["request"].data.get("reference_file_ids")
                if file_ids is not None:
                    instance.reference_files.set(file_ids)
            return instance


class MlModelListSerializer(serializers.ModelSerializer):
    defects = DefectSerializer(many=True)
    training_started_at = serializers.SerializerMethodField(read_only=True)
    training_finished_at = serializers.SerializerMethodField(read_only=True)
    created_by = UserSerializer(read_only=True)
    last_used_for_inference_at = serializers.SerializerMethodField(read_only=True)
    training_file_set_count = serializers.SerializerMethodField(read_only=True)
    inferenced_file_set_count = serializers.SerializerMethodField(read_only=True)

    def get_inferenced_file_set_count(self, instance):
        return FileSetInferenceQueue.objects.filter(ml_model=instance, status="FINISHED").count()

    def get_training_file_set_count(self, instance):
        try:
            return instance.training_session.trainingsessionfileset_set.filter(dataset_train_type="TRAIN").count()
        except TrainingSession.DoesNotExist:
            return None

    def get_last_used_for_inference_at(self, instance):
        try:
            return (
                FileSetInferenceQueue.objects.filter(ml_model=instance).order_by("-created_ts")[:1].first().created_ts
            )
        except AttributeError:
            return None

    def get_training_started_at(self, obj):
        try:
            return obj.training_session.started_at
        except TrainingSession.DoesNotExist:
            return None

    def get_training_finished_at(self, obj):
        try:
            return obj.training_session.finished_at
        except TrainingSession.DoesNotExist:
            return None

    class Meta:
        model = MlModel
        fields = [
            "id",
            "name",
            "path",
            "input_format",
            "output_format",
            "code",
            "version",
            "status",
            "is_stable",
            "subscription",
            "defects",
            "type",
            "use_case",
            "classification_type",
            "training_started_at",
            "training_finished_at",
            "created_ts",
            "created_by",
            "last_used_for_inference_at",
            "inferenced_file_set_count",
            "training_file_set_count",
            "training_session",
            "confidence_threshold",
        ]
        read_only_fields = ["classification_type"]


class MlModelDetailSerializer(serializers.ModelSerializer):
    defects = DefectSerializer(many=True)

    class Meta:
        model = MlModel
        fields = [
            "id",
            "name",
            "path",
            "input_format",
            "output_format",
            "code",
            "version",
            "status",
            "is_stable",
            "subscription",
            "defects",
            "type",
            "use_case",
            "classification_type",
        ]
        read_only_fields = ["classification_type"]


class MlModelCreateSerializer(serializers.ModelSerializer):
    pre_signed_post_data = serializers.SerializerMethodField(read_only=True)

    def __init__(self, instance=None, *args, **kwargs):
        super().__init__(instance=None, *args, **kwargs)
        self.MODEL_PATH_PREFIX = os.path.join(
            settings.MEDIA_ROOT, connection.tenant.schema_name, "models", uuid.uuid4().hex[:10]
        )

    def get_pre_signed_post_data(self, obj):
        if self.context.get("request", None):
            folder = self.context["request"].data.get("folder", [])
            presigned_post_data = {}
            s3 = S3Service()
            for file in folder:
                presigned_post_data[file] = s3.generate_pre_signed_post(os.path.join(self.MODEL_PATH_PREFIX, file))
            return presigned_post_data

    class Meta:
        model = MlModel
        fields = [
            "name",
            "path",
            "code",
            "use_case",
            "subscription",
            "type",
            "pre_signed_post_data",
            "version",
            "status",
            "defects",
            "classification_type",
        ]
        read_only_fields = ["classification_type"]

    def create(self, validated_data):
        with transaction.atomic():
            ml_model = super(MlModelCreateSerializer, self).create(validated_data)
            ml_model.path = {"invocation_path": self.MODEL_PATH_PREFIX}
            ml_model.save()
            if self.context.get("request", None):
                defects = self.context["request"].data.get("defects", None)
                if defects:
                    if type(defects) == str:
                        defects = map(int, defects.split(","))
                    ml_model_defects = [MlModelDefect(ml_model=ml_model, defect_id=int(defect)) for defect in defects]
                    MlModelDefect.objects.bulk_create(ml_model_defects)

                    existing_usecase_defect_ids = UseCaseDefect.objects.filter(
                        use_case_id=ml_model.use_case_id, defect_id__in=defects
                    ).values_list("defect_id", flat=True)
                    use_case_defects = [
                        UseCaseDefect(use_case_id=ml_model.use_case_id, defect_id=int(defect))
                        for defect in defects
                        if defect not in existing_usecase_defect_ids
                    ]
                    UseCaseDefect.objects.bulk_create(use_case_defects)
                for key, val in self.context["request"].FILES.items():
                    try:
                        # folder_path = os.path.join(self.MODEL_PATH_PREFIX, os.path.dirname(key))
                        folder_path = os.path.join(
                            self.MODEL_PATH_PREFIX.split("/")[-2],
                            self.MODEL_PATH_PREFIX.split("/")[-1],
                            os.path.dirname(key),
                        )
                        file_path = os.path.join(folder_path, os.path.basename(key))
                    except FileExistsError:
                        pass
                    default_storage.save(file_path, val)
            return ml_model


# class InferenceQueueSerializer(serializers.Serializer):
#     file_set_ids = serializers.ListField(required=True, allow_empty=False, allow_null=False)
#     ml_model_id = serializers.IntegerField(required=True, allow_null=False)
#
#     def create(self, validated_data):
#         for file_set_id in validated_data['file_set_ids']:
#             # kwargs = {
#             #     'file_set_id': file_set_id,
#             #     'ml_model_id': validated_data['ml_model_id']
#             # }
#             # celery_app.send_task('perform_file_set_inference', [], kwargs, queue='inference')
#             perform_file_set_inference.delay(file_set_id)
#         return validated_data
#
#     def update(self, instance, validated_data):
#         pass


class FileRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileRegion
        fields = [
            "id",
            "file",
            "ml_model",
            "defects",
            "ai_region",
            "region",
            "is_user_feedback",
            "is_removed",
            "created_by",
            "created_ts",
            "updated_by",
            "updated_ts",
            "classification_correctness",
            "detection_correctness",
        ]


class FileRegionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FileRegionHistory
        fields = [
            "id",
            "file",
            "ml_model",
            "defects",
            "ai_region",
            "region",
            "is_user_feedback",
            "file_region",
            "created_by",
            "created_ts",
            "updated_by",
            "updated_ts",
        ]


class FileSetInferenceQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileSetInferenceQueue
        fields = ["id", "file_set", "ml_model", "status"]


class UseCaseSerializer(serializers.ModelSerializer):
    ml_models = serializers.SerializerMethodField(read_only=True)
    file_set_count = serializers.SerializerMethodField(read_only=True)
    defect_count = serializers.SerializerMethodField(read_only=True)
    defects = DefectSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)

    def get_file_set_count(self, instance):
        return instance.file_sets.count()

    def get_defect_count(self, instance):
        return instance.defects.count()

    def get_ml_models(self, instance):
        return instance.ml_models.exclude(status="deleted").values_list("id", flat=True)

    def validate_type(self, value):
        if self.instance and value != self.instance.type:
            raise serializers.ValidationError("A UseCase type is immutable.")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            use_case = super().create(validated_data)
            if self.context.get("request", None):
                request = self.context.get("request")
                defect_ids = request.data.get("defects", [])
                use_case_defects = []
                for defect_id in defect_ids:
                    use_case_defects.append(UseCaseDefect(use_case=use_case, defect_id=defect_id))
                UseCaseDefect.objects.bulk_create(use_case_defects)
        return use_case

    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if self.context.get("request", None):
                request = self.context.get("request")
                defect_ids = request.data.get("defects", None)
                if defect_ids is not None:
                    instance.defects.clear()
                    use_case_defects = []
                    for defect_id in defect_ids:
                        use_case_defects.append(UseCaseDefect(use_case=instance, defect_id=defect_id))
                    UseCaseDefect.objects.bulk_create(use_case_defects)
        return instance

    class Meta:
        model = UseCase
        fields = [
            "id",
            "name",
            "type",
            "ml_models",
            "defects",
            "subscription",
            "created_ts",
            "created_by",
            "file_set_count",
            "defect_count",
            "classification_type",
            "automation_conditions",
        ]


class TrainingSessionFileSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingSessionFileSet
        fields = ["id", "training_session", "file_set", "defects"]
        read_only_fields = ["training_session", "file_set", "defects"]


class TrainingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingSession
        fields = ["id", "status", "old_ml_model", "new_ml_model", "started_at", "finished_at"]
        read_only_fields = ["new_ml_model"]

    def create(self, validated_data):
        with transaction.atomic():
            new_ml_model_name = self.context["request"].data.get("new_ml_model_name", None)
            old_ml_model = validated_data["old_ml_model"]
            ml_model_code = old_ml_model.code
            new_version = MlModel.objects.filter(code=ml_model_code).aggregate(Max("version"))["version__max"]
            # ToDo: Either add a db trigger or add an after save trigger to update version after model creation
            new_version += 1
            new_ml_model: MlModel = MlModel.objects.create(
                name=new_ml_model_name,
                code=ml_model_code,
                version=new_version,
                status="draft",
                use_case=old_ml_model.use_case,
                subscription=old_ml_model.subscription,
            )
            validated_data["new_ml_model"] = new_ml_model
            training_session: TrainingSession = super(TrainingSessionSerializer, self).create(validated_data)

            # If it's re-training then copping defects and filesets from older training session
            if old_ml_model:
                new_ml_model.copy_defects_from(old_ml_model, training_session.created_by.id)
                training_session.copy_files_from_model(old_ml_model, training_session.created_by.id)

        # this call could be sent to queue and made async
        training_session.copy_gt_defects()
        return training_session


class UserClassificationSerializer(serializers.ModelSerializer):
    defects = DefectSerializer(many=True, read_only=True)

    def validate(self, attrs):
        # During update, we shouldn't be able to update the user field
        if self.instance and attrs.get("user", None) is not None and self.instance.user != attrs["user"]:
            raise ValidationError("user field is non editable")
        # During creation, user field in context gets higher priority
        if not self.instance and self.context.get("user", None):
            attrs["user"] = self.context.get("user")

        # During update, we shouldn't be able to update the file field
        if self.instance and attrs.get("file", None) is not None and self.instance.file != attrs["file"]:
            raise ValidationError("file field is non editable")
        if not self.instance and not attrs.get("file", None):
            raise ValidationError("file is required")

        # ToDo: We are adding this logic to validate single label from multi label everywhere
        #  Eg. It's repeated in services as well. It needs to be some how moved to a single place like models
        #  or managers
        defect_ids = self.context.get("defects", None)
        if defect_ids:
            if attrs.get("is_no_defect", None) is True:
                raise ValidationError("Can't insert defects and set is_no_defect as True.")
            if len(defect_ids) > 1:
                use_case_type = UseCase.objects.get(file_sets__files__id=attrs["file"].id).classification_type
                if use_case_type == "SINGLE_LABEL":
                    raise ValidationError("Can't insert multiple defects for a single label use case type.")

        return super(UserClassificationSerializer, self).validate(attrs)

    def create(self, validated_data):
        with transaction.atomic():
            user_classification = super().create(validated_data)
            defect_ids = self.context.get("defects", None)
            if user_classification.is_no_defect is False and defect_ids:
                user_classification_defects = []
                for defect_id in defect_ids:
                    user_classification_defects.append(
                        UserClassificationDefect(classification=user_classification, defect_id=defect_id)
                    )
                UserClassificationDefect.objects.bulk_create(user_classification_defects)
            # ToDo: The following line to copy to GT should be removed once the UI has a feature to assign the GT
            user_classification.copy_to_gt()
        return user_classification

    def update(self, instance, validated_data):
        with transaction.atomic():
            user_classification = super().update(instance, validated_data)
            defect_ids = self.context.get("defects", None)
            if user_classification.is_no_defect is False and defect_ids:
                user_classification_defects = []
                UserClassificationDefect.objects.filter(classification=user_classification).delete()
                for defect_id in defect_ids:
                    user_classification_defects.append(
                        UserClassificationDefect(classification=user_classification, defect_id=defect_id)
                    )
                UserClassificationDefect.objects.bulk_create(user_classification_defects)
            if user_classification.is_no_defect is True:
                UserClassificationDefect.objects.filter(classification=user_classification).delete()
            # ToDo: The following line to copy to GT should be removed once the UI has a feature to assign the GT
            user_classification.copy_to_gt()
        return instance

    class Meta:
        model = UserClassification
        fields = ["id", "is_no_defect", "file", "defects", "user", "created_ts", "updated_ts"]
        extra_kwargs = {"user": {"required": False}, "file": {"required": False}}
        validators = []


class UserDetectionRegionSerializer(serializers.ModelSerializer):
    defects = DefectSerializer(many=True, read_only=True)
    region = serializers.SerializerMethodField(read_only=True)

    def get_region(self, instance):
        coords = instance.region.coords
        return {
            "type": "box",
            "coordinates": {
                "x": coords[0][0][0],
                "y": coords[0][0][1],
                "h": coords[0][2][1] - coords[0][0][1],
                "w": coords[0][2][0] - coords[0][0][0],
            },
        }

    class Meta:
        model = ModelDetectionRegion
        fields = ["id", "defects", "region"]


class UserDetectionSerializer(serializers.ModelSerializer):
    # defects = DefectSerializer(many=True, read_only=True)
    detection_regions = UserDetectionRegionSerializer(many=True, read_only=True)

    def validate(self, attrs):
        # During update, we shouldn't be able to update the user field
        if self.instance and attrs.get("user", None) is not None and self.instance.user != attrs["user"]:
            raise ValidationError("user field is non editable")
        # During creation, user field in context gets higher priority
        if not self.instance and self.context.get("user", None):
            attrs["user"] = self.context.get("user")

        # During update, we shouldn't be able to update the file field
        if self.instance and attrs.get("file", None) is not None and self.instance.file != attrs["file"]:
            raise ValidationError("file field is non editable")
        if not self.instance and not attrs.get("file", None):
            raise ValidationError("file is required")

        return super(UserDetectionSerializer, self).validate(attrs)

    def create(self, validated_data):
        with transaction.atomic():
            user_detection = super().create(validated_data)
            if user_detection.is_no_defect is False and self.context.get("detection_regions", None):
                detection_regions = self.context.get("detection_regions")
                for detection_region_data in detection_regions:
                    region = detection_region_data["region"]["coordinates"]
                    polygon_region = Polygon(
                        (
                            (region["x"], region["y"]),
                            (region["x"] + region["w"], region["y"]),
                            (region["x"] + region["w"], region["y"] + region["h"]),
                            (region["x"], region["y"] + region["h"]),
                            (region["x"], region["y"]),
                        )
                    )
                    detection_region = UserDetectionRegion.objects.create(
                        region=polygon_region,
                        detection=user_detection,
                    )
                    user_detection_defects = []
                    for defect_id in detection_region_data["defects"]:
                        user_detection_defects.append(
                            UserDetectionRegionDefect(detection_region=detection_region, defect_id=defect_id)
                        )
                    UserDetectionRegionDefect.objects.bulk_create(user_detection_defects)
            # ToDo: The following line to copy to GT should be removed once the UI has a feature to assign the GT
            user_detection.copy_to_gt()
            return user_detection

    def update(self, instance, validated_data):
        with transaction.atomic():
            user_detection = super().update(instance, validated_data)
            if user_detection.is_no_defect is False and self.context.get("detection_regions", None):
                UserDetectionRegion.objects.filter(detection=user_detection).delete()
                detection_regions = self.context.get("detection_regions")
                for detection_region_data in detection_regions:
                    region = detection_region_data["region"]["coordinates"]
                    region_polygon = Polygon(
                        (
                            (region["x"], region["y"]),
                            (region["x"] + region["w"], region["y"]),
                            (region["x"] + region["w"], region["y"] + region["h"]),
                            (region["x"], region["y"] + region["h"]),
                            (region["x"], region["y"]),
                        )
                    )
                    detection_region = UserDetectionRegion.objects.create(
                        region=region_polygon,
                        detection=user_detection,
                    )
                    user_detection_defects = []
                    for defect_id in detection_region_data["defects"]:
                        user_detection_defects.append(
                            UserDetectionRegionDefect(detection_region=detection_region, defect_id=defect_id)
                        )
                    UserDetectionRegionDefect.objects.bulk_create(user_detection_defects)
            if user_detection.is_no_defect is True:
                UserDetectionRegion.objects.filter(detection=user_detection).delete()
            # ToDo: The following line to copy to GT should be removed once the UI has a feature to assign the GT
            user_detection.copy_to_gt()
            return user_detection

    class Meta:
        model = UserDetection
        fields = ["id", "is_no_defect", "file", "detection_regions", "user", "created_ts", "updated_ts"]
        extra_kwargs = {"user": {"required": False}, "file": {"required": False}}
        validators = []


class MLModelClassificationSerializer(serializers.ModelSerializer):
    defects = DefectSerializer(many=True, read_only=True)
    # TODO: remove this serializer, it is there to support image handler so that it can get defects and percentage
    classifications = serializers.SerializerMethodField("_get_classifications")

    def _get_classifications(self, obj):
        return obj.model_classification_annotations.values("defect", "confidence", "defect__organization_defect_code")

    class Meta:
        model = ModelClassification
        fields = "__all__"
        depth = 1


# class ModelDetectionRegionDefectSerializer(serializers.ModelSerializer):
#     defect = DefectSerializer(read_only=True)
#
#     class Meta:
#         model = ModelDetectionRegionDefect
#         fields = ["id", "confidence", "defect"]


class ModelDetectionRegionSerializer(serializers.ModelSerializer):
    # region_defects = ModelDetectionRegionDefectSerializer(
    #     source="model_detection_region_annotations", many=True, read_only=True
    # )
    defects = DefectSerializer(many=True, read_only=True)
    region = serializers.SerializerMethodField(read_only=True)

    def get_region(self, instance):
        coords = instance.region.coords
        return {
            "type": "box",
            "coordinates": {
                "x": coords[0][0][0],
                "y": coords[0][0][1],
                "h": coords[0][1][1] - coords[0][0][1],
                "w": coords[0][2][0] - coords[0][0][0],
            },
        }

    class Meta:
        model = ModelDetectionRegion
        fields = ["id", "defects", "region"]


class MLModelDetectionSerializer(serializers.ModelSerializer):
    detection_regions = ModelDetectionRegionSerializer(many=True, read_only=True)

    class Meta:
        model = ModelDetection
        fields = ["id", "file", "ml_model", "is_no_defect", "detection_regions"]
        depth = 1


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "description"]


class WaferMapSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    wafer_url = serializers.SerializerMethodField(read_only=True)

    def get_wafer_url(self, instance):
        return instance.get_pre_signed_url()

    def create(self, validated_data):
        image_path = (
            os.path.join(
                settings.MEDIA_ROOT,
                connection.tenant.schema_name,
                "wafers",
                add_uuid_to_file_name(validated_data["organization_wafer_id"]),
            )
            + ".png"
        )
        pre_signed_post_data = S3Service().generate_pre_signed_post(image_path)
        try:
            # ToDo: There should be a retry mechanism for when DS API is down
            response = WaferMap.create_wafer_image(
                validated_data.get("meta_data"), validated_data.get("coordinate_meta_info"), pre_signed_post_data
            )
            if response.get("defect_pattern_info"):
                validated_data["defect_pattern_info"] = response.get("defect_pattern_info")
                del response["defect_pattern_info"]
            validated_data["img_meta_info"] = response
            validated_data["image_path"] = image_path
        except ImproperlyConfigured as e:
            pass
        return super(WaferMapSerializer, self).create(validated_data)

    class Meta:
        model = WaferMap
        fields = [
            "id",
            "organization_wafer_id",
            "meta_data",
            "tags",
            "img_meta_info",
            "wafer_url",
            "status",
            "coordinate_meta_info",
            "defect_pattern_info",
        ]


class WaferMapReadSerializer(serializers.ModelSerializer):
    total_images = serializers.SerializerMethodField(read_only=True)
    upload_session_name = serializers.SerializerMethodField(read_only=True)
    wafer_url = serializers.SerializerMethodField(read_only=True)

    def update(self, instance, validated_data):
        """[
        when the caller wants to update the status to manually_classified and image handler queue is present,
        then sent message to queue and once the message is consumed, then consumer will update the status
        otherwise status will be updated as per the caller's request]
        """
        if (
            instance.status != validated_data.get("status")
            and validated_data.get("status") == "manually_classified"
            and IMAGE_HANDLER_QUEUE_URL
        ):
            result = (
                WaferMap.objects.filter(id=instance.id, file_sets__files__gt_classifications__isnull=False)
                .annotate(
                    file_set_id=F("file_sets__id"),
                    defect_id=F("file_sets__files__gt_classifications__defects__organization_defect_code"),
                )
                .values("file_set_id")
                .annotate(defects=ArrayAgg("defect_id"))
                .values("file_set_id", "defects")
            )
            message = {"type": "update_klarf_file", "files": list(result)}
            inference_output_queue(message)
        else:
            instance = super(WaferMapReadSerializer, self).update(instance, validated_data)
        return instance

    def get_wafer_url(self, instance):
        return instance.get_pre_signed_url()

    def get_total_images(self, instance):
        return File.objects.filter(file_set__wafer=instance).count()

    def get_upload_session_name(self, instance):
        queryset = FileSet.objects.filter(wafer=instance).values_list("upload_session__name", flat=True)
        return queryset.first()

    class Meta:
        model = WaferMap
        fields = [
            "id",
            "organization_wafer_id",
            "status",
            "wafer_url",
            "created_ts",
            "updated_ts",
            "total_images",
            "upload_session_name",
        ]


class FilesetDefectNamesResponse(serializers.Serializer):
    id = serializers.IntegerField()
    files__gt_classifications__gt_classification_annotations__defect__name = serializers.CharField(required=False)
    files__model_classifications__model_classification_annotations__defect__name = serializers.CharField(
        required=False
    )
    files__model_classifications__ml_model__id = serializers.IntegerField(required=False)


class TaskResultSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField(read_only=True)
    description = serializers.SerializerMethodField(read_only=True)

    def get_task_args(self, instance):
        return ast.literal_eval(str(instance.task_args))[0]

    def get_task_name(self, instance):
        splitted = instance.task_name.split(".")
        return splitted[len(splitted) - 1]

    def get_description(self, instance):
        meta = self.get_task_args(instance)
        return meta.get("description") if meta else None

    class Meta:
        model = TaskResult
        fields = ["task_id", "task_name", "status", "date_created", "description"]
