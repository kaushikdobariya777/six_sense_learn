from datetime import datetime

import pytz
from django.db.models import Subquery
from django_filters import rest_framework as django_filters
from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.classif_ai.models import FileSetInferenceQueue, MlModel
from apps.classif_ai.serializers import FileSetInferenceQueueSerializer
from apps.classif_ai.services import AnalysisService
from apps.classif_ai.views.v2.model_annotation_views import IsSuperUser
from common.views import BaseViewSet


class FileSetInferenceQueueViewSet(BaseViewSet):
    serializer_class = FileSetInferenceQueueSerializer
    queryset = FileSetInferenceQueue.objects.all()
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter]
    ordering = ["-created_ts"]
    filterset_fields = ("file_set_id", "ml_model_id", "status")

    def get_permissions(self):
        if self.action in ["update", "partial_update"]:
            return [IsSuperUser()]
        else:
            return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["GET"], detail=False)
    def progress_status(self, request):
        ml_model_ids = []
        file_set_filters = {}
        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_ids = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "file_set_id__in":
                file_set_filters["id__in"] = val.split(",")
            elif key == "upload_session_id__in":
                file_set_filters[key] = val.split(",")
            else:
                file_set_filters[key] = val

        analysis_service = AnalysisService(file_set_filters)
        file_set_ids = analysis_service.file_sets().values_list("id", flat=True)

        total_count = (
            FileSetInferenceQueue.objects.filter(
                ml_model_id__in=ml_model_ids,
                file_set_id__in=file_set_ids,
            )
            .values("file_set_id", "ml_model_id")
            .distinct()
            .count()
        )

        finished_count = (
            FileSetInferenceQueue.objects.filter(
                ml_model_id__in=ml_model_ids, file_set_id__in=file_set_ids, status="FINISHED"
            )
            .values("file_set_id", "ml_model_id")
            .distinct()
            .count()
        )

        # To get the failed count do the following steps
        # 1. Pick all latest (based on created_ts) queues with distinct file set id and ml model id
        # 2. From this, filter for status = 'FAILED' and take the count
        qs = (
            FileSetInferenceQueue.objects.filter(ml_model_id__in=ml_model_ids, file_set_id__in=file_set_ids)
            .distinct("file_set_id", "ml_model_id")
            .order_by("file_set_id", "ml_model_id", "-created_ts")
            .values("id", "status")
        )
        failed_count = FileSetInferenceQueue.objects.filter(
            status="FAILED", id__in=Subquery(qs.values_list("id"))
        ).count()

        return Response(
            {
                "finished": finished_count,
                "failed": failed_count,
                "total": total_count,
            },
        )

    @action(
        methods=[
            "POST",
        ],
        detail=False,
    )
    def bulk_create(self, request):
        ml_model_ids = []
        file_set_filters = {}
        for key, val in request.data.items():
            if key == "ml_model_id__in":
                ml_model_ids = val
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            else:
                file_set_filters[key] = val
        analysis_service = AnalysisService(file_set_filters)
        file_sets = analysis_service.file_sets().order_by("id").values("id", "use_case_id")
        batch_size = 1000
        total = file_sets.count()
        file_set_inference_queues = []
        ml_models = MlModel.objects.filter(id__in=ml_model_ids).values("id", "use_case_id")
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            for file_set in file_sets[start:end]:
                if file_set["use_case_id"]:
                    for ml_model in ml_models:
                        if ml_model["use_case_id"] == file_set["use_case_id"]:
                            file_set_inference_queues.append(
                                FileSetInferenceQueue(
                                    file_set_id=file_set["id"], ml_model_id=ml_model["id"], status="PENDING"
                                )
                            )
        FileSetInferenceQueue.objects.partial_create(file_set_inference_queues)
        return Response(status=status.HTTP_201_CREATED)
