import importlib
import logging
from datetime import datetime, MINYEAR

import pytz
from django.db import connection, transaction
from django.db.models import Q, Prefetch, Value
from django_filters import rest_framework as django_filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination, LimitOffsetPagination

from apps.classif_ai.filters import FileSetFilterSet, filter_file_sets_with_train_type
from apps.classif_ai.helpers import get_default_model_for_file_set, JSONBSet
from apps.classif_ai.models import (
    FileSet,
    MlModelDeploymentHistory,
    UseCase,
    MlModel,
    FileRegion,
    Defect,
    UploadSession,
    TrainingSession,
    FileRegionHistory,
    File,
    FileSetInferenceQueue,
)
from apps.classif_ai.serializers import (
    FileSetCreateSerializer,
    FileSetInferenceQueueSerializer,
    FileReadSerializer,
    MlModelDetailSerializer,
    FilesetDefectNamesResponse,
)
from apps.classif_ai.services import AnalysisService
from apps.classif_ai.tasks import copy_images_to_folder
from common.views import BaseViewSet
from sixsense.settings import PROJECT_START_DATE

logger = logging.getLogger(__name__)


class FileSetPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "limit"
    ordering = "-id"

    def __init__(self, ordering):
        if ordering:
            self.ordering = ordering


class FileSetDefectNamesPagination(LimitOffsetPagination):
    def get_paginated_response(self, data):
        response_data = {}
        for item in data:
            obj = {
                "id": item.get("id"),
            }
            if item.get("files__model_classifications__ml_model__id"):
                obj["ml_model_id"] = item.get("files__model_classifications__ml_model__id")
            if item.get("files__model_classifications__model_classification_annotations__defect__name"):
                obj["model_defect_names"] = [
                    item.get("files__model_classifications__model_classification_annotations__defect__name")
                ]
            if item.get("files__gt_classifications__gt_classification_annotations__defect__name"):
                obj["gt_defect_names"] = [
                    item.get("files__gt_classifications__gt_classification_annotations__defect__name")
                ]
            response_data.update({item["id"]: obj})
        return Response(
            {
                "count": self.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": response_data,
            }
        )


class FileSetDefectNamesCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "limit"
    ordering = "-id"

    def __init__(self, ordering):
        if ordering:
            self.ordering = ordering

    def get_paginated_response(self, data):
        response_data = {}
        for item in data:
            obj = {
                "id": item.get("id"),
            }
            if item.get("files__model_classifications__ml_model__id"):
                obj["ml_model_id"] = item.get("files__model_classifications__ml_model__id")
            if item.get("files__model_classifications__model_classification_annotations__defect__name"):
                obj["model_defect_names"] = [
                    item.get("files__model_classifications__model_classification_annotations__defect__name")
                ]
            if item.get("files__gt_classifications__gt_classification_annotations__defect__name"):
                obj["gt_defect_names"] = [
                    item.get("files__gt_classifications__gt_classification_annotations__defect__name")
                ]
            response_data.update({item["id"]: obj})
        return Response(
            {
                "count": self.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": response_data,
            }
        )


class FileSetViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FileSetCreateSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = FileSetFilterSet
    parser_classes = [MultiPartParser, JSONParser]

    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, "_paginator"):
            # NOTE:
            # if cursor = '', then file set pagination will be used
            # if cursor is None, then limit offset is used by default
            if self.request.query_params.get("cursor") is not None:
                self._paginator = FileSetPagination(self.request.query_params.get("ordering"))
            else:
                self._paginator = LimitOffsetPagination()

        return self._paginator

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        query = Q()
        order = ["-id"]
        for key in self.request.query_params:
            if key.startswith("meta_info__"):
                val = self.request.query_params.get(key).split(",")
                if val[0]:
                    expr = {f"{key}": val}
                    query &= Q(**expr)
                else:
                    key1 = key.split("__")[1]
                    query &= ~Q(meta_info__has_key=key1) | Q(**{f"{key}": [None, ""]})
            if key == "ordering":
                order = self.request.query_params.get(key).split(",")
        queryset = (
            FileSet.objects.prefetch_related(
                "files",
                "files__gt_classifications__defects",
                "files__gt_detections__detection_regions__gt_detection_region_annotation__defect",
            )
            .select_related("upload_session")
            .filter(query)
            .order_by(*order)
        )
        return queryset

    def perform_create(self, serializer):
        super(BaseViewSet, self).perform_create(serializer)
        if self.request.data.get("perform_inference"):
            ml_model = get_default_model_for_file_set(serializer.instance)
            inference_queue_serializer = FileSetInferenceQueueSerializer(
                data={"file_set": serializer.instance.id, "ml_model": ml_model.id}
            )
            if inference_queue_serializer.is_valid():
                inference_queue_serializer.save()
            else:
                logger.info("Inference Queue could not be created")
                logger.error(inference_queue_serializer.errors)

    def perform_destroy(self, instance):
        # instance.is_deleted = True
        # instance.save()
        with transaction.atomic():
            file_set_inference_queues = FileSetInferenceQueue.objects.filter(file_set=instance)
            files = File.objects.filter(file_set=instance)
            file_regions_with_ai_region_is_not_null = FileRegion.objects.filter(
                file__in=files, ai_region_id__isnull=False
            )
            file_regions_with_ai_region_is_null = FileRegion.objects.filter(file__in=files, ai_region_id__isnull=True)
            file_region_history = FileRegionHistory.objects.filter(file__in=files)
            file_region_history.delete()
            file_regions_with_ai_region_is_not_null.delete()
            file_regions_with_ai_region_is_null.delete()
            # ToDo: Delete the actual files from the storage as well
            files.delete()
            file_set_inference_queues.delete()
            instance.delete()

    @action(methods=["PATCH"], detail=False)
    def bulk_update(self, request):
        file_set_ids = request.data.get("file_sets", None)
        data = request.data.get("data", None)
        valid_fields = ["is_bookmarked"]
        if not (file_set_ids or data):
            return Response("Please send the file set ids and the data to update", status=status.HTTP_400_BAD_REQUEST)
        if not set(data.keys()).issubset(valid_fields):
            return Response("Invalid field name", status=status.HTTP_400_BAD_REQUEST)
        FileSet.objects.filter(id__in=file_set_ids).update(**data)
        return Response(f"Succesfully updated {len(file_set_ids)} file sets.")

    @action(
        methods=[
            "GET",
        ],
        detail=False,
    )
    def related_defects(self, request):
        file_set_filters = {}
        ml_model_filters = {}
        limit = None
        offset = None
        use_case = None
        ml_model_id = None

        for key, val in request.query_params.items():
            if key == "ml_model_id":
                ml_model_id = int(val)
            elif key == "use_case_id__in":
                ml_model_filters["use_case_id__in"] = val.split(",")
                use_case = UseCase.objects.filter(id=val).first()
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "limit":
                limit = int(val)
            elif key == "offset":
                offset = int(val)
            else:
                file_set_filters[key] = val.split(",")
        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        ml_model_ids = MlModel.objects.filter(use_case=use_case)
        # ToDo: This query is not considering cases where user has added defects to images on which ai didn't predict
        #  anything
        file_sets = FileSet.objects.filter(
            files__in=analysis_service.files().filter(
                Q(file_regions__detection_correctness__isnull=False)
                | Q(file_regions__classification_correctness__isnull=False)
                | Q(file_regions__is_user_feedback=True, file_regions__ai_region__isnull=True),
                file_regions__ml_model__in=ml_model_ids,
            )
        ).order_by("id")
        count = file_sets.count()
        if count == 0:
            return Response([])
        if limit:
            file_sets = file_sets[offset : limit + offset]
        elif offset:
            file_sets = file_sets[offset:]

        file_sets = file_sets.prefetch_related(
            Prefetch(
                "files__file_regions",
                queryset=FileRegion.objects.filter(
                    Q(detection_correctness__isnull=False)
                    | Q(classification_correctness__isnull=False)
                    | Q(is_user_feedback=True)
                ).order_by("-updated_ts"),
            )
        )
        defects_id_name_map = {}
        for defect in Defect.objects.all():
            defects_id_name_map[defect.id] = defect.name
        response = []
        defects_with_count = {}
        for file_set in file_sets:
            defects = {}
            # Find which model to use to pick up the latest feedback
            ml_model_id_for_gt = None
            latest_updated_ts = datetime(MINYEAR, 1, 1, 0, 0, 0, 0, pytz.UTC)
            for file in file_set.files.all():
                if file.file_regions.first():
                    if file.file_regions.first().updated_ts > latest_updated_ts:
                        ml_model_id_for_gt = file.file_regions.first().ml_model_id
                        latest_updated_ts = file.file_regions.first().updated_ts
            for file in file_set.files.all():
                # Collect all valid GT file regions for ml_model_id_for_gt
                if defects.get(file.id, None) is None:
                    defects[file.id] = []
                for region in file.file_regions.all():
                    # ToDo: belongs_to_gt method is not available. Write a logic for that
                    if region.ml_model_id == ml_model_id_for_gt and region.is_gt_region():
                        for defect_id in region.defects:
                            # defects[file.id].append(FileRegionSerializer(instance=region).data)
                            if not defects_with_count.get(defect_id):
                                defects_with_count[defect_id] = 0
                            defects_with_count[defect_id] += 1
        if ml_model_id:
            try:
                training_session = TrainingSession.objects.filter(new_ml_model_id=ml_model_id).first()
                # Exclude all file sets that we've already seen.
                training_session_file_sets = training_session.trainingsessionfileset_set.filter(
                    ~Q(file_set__in=file_sets)
                )
                for tfs in training_session_file_sets:
                    for _, regions in tfs.defects.items():
                        for region in regions:
                            for defect_id, val in region["defects"].items():
                                if not defects_with_count.get(defect_id):
                                    defects_with_count[defect_id] = 0
                                defects_with_count[defect_id] += 1
            except AttributeError:
                pass

        for defect_id, count in defects_with_count.items():
            defect_id = int(defect_id)
            defect_name = defects_id_name_map[defect_id]
            response.append({"defect": {"id": defect_id, "name": defect_name}, "count": count})

        return Response(response)

    @action(
        methods=[
            "GET",
        ],
        detail=True,
    )
    def last_deployed_model(self, request, pk):
        ml_model_ids = (
            FileSetInferenceQueue.objects.filter(file_set_id=pk, status="FINISHED")
            .order_by("-created_ts")
            .values_list("ml_model_id", flat=True)
        )
        if len(ml_model_ids) == 0:
            return Response({"ml_model": None})
        else:
            last_deployed_model = (
                MlModelDeploymentHistory.objects.filter(ml_model_id__in=ml_model_ids).order_by("starts_at").last()
            )
            if last_deployed_model:
                ml_model = MlModel.objects.get(id=last_deployed_model.ml_model_id)
            else:
                ml_model = MlModel.objects.get(id=ml_model_ids[0])
            serializer = MlModelDetailSerializer(instance=ml_model)
            return Response({"ml_model": serializer.data})

    @action(methods=["GET"], detail=False)
    def use_cases(self, request):
        file_set_filters = {}
        for key, val in request.query_params.items():
            if key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key in ["is_bookmarked", "is_deleted"]:
                if val == "True" or val == "true":
                    file_set_filters[key] = True
                else:
                    file_set_filters[key] = False
            else:
                file_set_filters[key] = val.split(",")

        analysis_service = AnalysisService(file_set_filters)
        use_cases = UseCase.objects.filter(
            id__in=analysis_service.file_sets().values_list("use_case_id", flat=True)
        ).values("id", "name", "type")
        return Response(list(use_cases))

    @action(
        methods=[
            "GET",
        ],
        detail=False,
    )
    def defects(self, request):
        file_set_filters = {}
        limit = None
        offset = None
        count = None
        use_case = None
        train_types = None
        training_ml_model_ids = []

        for key, val in request.query_params.items():
            if key == "use_case_id__in":
                use_case = UseCase.objects.filter(id=val).first()
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "limit":
                limit = int(val)
            elif key == "offset":
                offset = int(val)
            elif key == "train_type__in":
                train_types = val.split(",")
            elif key == "training_ml_model__in":
                training_ml_model_ids = val.split(",")
                training_ml_model_ids = [int(_id) for _id in training_ml_model_ids]
            else:
                file_set_filters[key] = val.split(",")

        analysis_service = AnalysisService(file_set_filters)
        ml_model_ids = MlModel.objects.filter(use_case=use_case)
        # ToDo: This query is not considering cases where user has added defects to images on
        # which ai didn't predict anything
        file_sets = FileSet.objects.filter(
            files__in=analysis_service.files().filter(
                Q(file_regions__detection_correctness__isnull=False)
                | Q(file_regions__classification_correctness__isnull=False)
                | Q(file_regions__is_user_feedback=True, file_regions__ai_region__isnull=True),
                file_regions__ml_model__in=ml_model_ids,
            )
        ).order_by("id")
        if train_types is not None:
            file_sets = filter_file_sets_with_train_type(file_sets, train_types, training_ml_model_ids)

        count = file_sets.count()
        if count == 0:
            return Response({"count": 0, "file_sets": []})
        if limit:
            file_sets = file_sets[offset : limit + offset]
        elif offset:
            file_sets = file_sets[offset:]

        file_sets = file_sets.prefetch_related(
            Prefetch(
                "files__file_regions",
                queryset=FileRegion.objects.filter(
                    Q(detection_correctness__isnull=False)
                    | Q(classification_correctness__isnull=False)
                    | Q(is_user_feedback=True)
                ).order_by("-updated_ts"),
            )
        )
        defects_id_name_map = {}
        for defect in Defect.objects.all():
            defects_id_name_map[defect.id] = defect.name
        file_sets_with_defects = []
        for file_set in file_sets:
            defects = {}
            # Find which model to use to pick up the latest feedback
            ml_model_id_for_gt = None
            latest_updated_ts = datetime(MINYEAR, 1, 1, 0, 0, 0, 0, pytz.UTC)
            file_set_with_defects = {"file_set_id": file_set.id, "files": []}
            for file in file_set.files.all():
                if file.file_regions.first():
                    if file.file_regions.first().updated_ts > latest_updated_ts:
                        ml_model_id_for_gt = file.file_regions.first().ml_model_id
                        latest_updated_ts = file.file_regions.first().updated_ts
            for file in file_set.files.all():
                file_data = FileReadSerializer(instance=file).data
                # Collect all valid GT file regions for ml_model_id_for_gt
                if defects.get(file.id, None) is None:
                    defects[file.id] = []
                for region in file.file_regions.all():
                    # ToDo: belongs_to_gt method is not available. Write a logic for that
                    if region.ml_model_id == ml_model_id_for_gt and region.is_gt_region():
                        for defect_id in region.defects:
                            # defects[file.id].append(FileRegionSerializer(instance=region).data)
                            defect_name = defects_id_name_map[int(defect_id)]
                            if file_data.get("defects", None) is None:
                                file_data["defects"] = {}
                            if defect_name in file_data["defects"]:
                                file_data["defects"][defect_name] += 1
                            else:
                                file_data["defects"][defect_name] = 1
                file_set_with_defects["files"].append(file_data)
            if file_set_with_defects["files"]:
                file_sets_with_defects.append(file_set_with_defects)

        response = {"count": count, "file_sets": file_sets_with_defects}

        return Response(response)

    @action(methods=["GET"], detail=False)
    def defect_names(self, request):
        query_params = request.query_params
        file_set_filter = FileSetFilterSet(query_params, queryset=FileSet.objects.all(), request=request)
        queryset = file_set_filter.qs
        # conditional fields
        # if nothing is passed, all fields are sent else the user can request the fields
        fields = ["id"]
        if query_params.get("fields") is None or query_params.get("fields") == "":
            fields = ["id"]
        else:
            needed_fields = query_params.get("fields").split(",")
            mapping = {
                "model_defect_names": [
                    "files__model_classifications__model_classification_annotations__defect__name",
                    "files__model_classifications__ml_model__id",
                ],
                "gt_defect_names": ["files__gt_classifications__gt_classification_annotations__defect__name"],
            }
            for field in needed_fields:
                fields = fields + mapping.get(field)

        queryset_data = queryset.values(*fields).distinct()
        if self.request.query_params.get("cursor") is not None:
            paginator = FileSetDefectNamesCursorPagination(self.request.query_params.get("ordering"))
        else:
            paginator = FileSetDefectNamesPagination()
        page = paginator.paginate_queryset(queryset_data, request)
        serializer = FilesetDefectNamesResponse(page, many=True)
        response = paginator.get_paginated_response(serializer.data)
        return response

    @action(detail=False, methods=["POST"], url_name="copy", url_path="copy")
    def copy(self, request):
        # TODO: add serializer for validation
        # TODO: should not fileset filter be sent as request params and upload session in body?
        input_data = request.data
        upload_session_id = input_data.get("upload_session_id")
        if not upload_session_id:
            return Response(
                {"success": False, "message": "upload_session_id is required field"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_set_filters = input_data.get("file_set_filters")
        if not file_set_filters:
            return Response(
                {"success": False, "message": "file_set_filters is required field"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        upload_session: UploadSession = UploadSession.objects.get(id=upload_session_id)
        input_data["description"] = "Copy Images to folder {}".format(upload_session.name)
        task_id = copy_images_to_folder.delay(input_data, schema=connection.schema_name)
        return Response(
            {"success": True, "message": "Images are being copied", "task_id": task_id.id},
            status=status.HTTP_200_OK,
        )


@api_view(["GET"])
@permission_classes((permissions.IsAuthenticated,))
def file_set_meta_info_distinct_values(request, field):
    logger.info("Requested for fileset meta info distinct values for field: '%s'" % field)
    query = Q()
    date__gte = PROJECT_START_DATE
    date__lte = datetime.now()

    for key, val in request.query_params.items():
        if key == "subscription_id":
            query &= Q(subscription_id=val)
        elif key == "date__gte":
            date__gte = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        elif key == "date__lte":
            date__lte = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
    query &= Q(created_ts__lte=date__lte, created_ts__gte=date__gte)

    result = FileSet.objects.filter(query).values_list(f"meta_info__{field}", flat=True).distinct().order_by()
    return Response({"data": result}, status=status.HTTP_200_OK)


class UploadMetaInfoViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def partial_update(self, request, *args, **kwargs):
        upload_session_id = request.data.get("upload_session_id", None)
        file = request.FILES.get("file", None)
        if not upload_session_id or not file:
            return Response(
                {"message": "Upload Session id or meta info file is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        upload_session = UploadSession.objects.get(id=upload_session_id)
        file_sets = upload_session.file_sets.all()
        subscription_id = upload_session.subscription_id
        helpers_module = importlib.import_module("apps.classif_ai.helpers")
        file = file.file.read()
        try:
            header_meta_info = getattr(helpers_module, connection.tenant.schema_name + "_header_xml_to_dict")(
                meta_file_path=file, subscription_id=subscription_id
            )
        except AttributeError:
            header_meta_info = {}
        try:
            yield_meta_info = getattr(helpers_module, connection.tenant.schema_name + "_yield_xml_to_dict")(
                meta_file_path=file, subscription_id=subscription_id
            )
        except AttributeError:
            yield_meta_info = {}
        for head_item, yield_item in zip(header_meta_info.items(), yield_meta_info.items()):
            with transaction.atomic():
                file_sets.update(
                    meta_info=JSONBSet("meta_info", [head_item[0]], Value('"%s"' % head_item[1]), Value(True))
                )
                file_sets.update(
                    meta_info=JSONBSet("meta_info", [yield_item[0]], Value('"%s"' % yield_item[1]), Value(True))
                )
        return Response({"success": True}, status=status.HTTP_200_OK)
