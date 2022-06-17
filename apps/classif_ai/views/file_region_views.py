from apps.classif_ai.services import AnalysisService, BulkFeedbackService
import logging
from datetime import datetime
import pytz

from django.db import transaction
from django.core.exceptions import ValidationError
from django_filters import rest_framework as django_filters
from rest_framework import permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.classif_ai.models import FileRegion, FileRegionHistory, MlModel
from apps.classif_ai.serializers import FileRegionSerializer, FileRegionHistorySerializer
from common.views import BaseViewSet


class FileRegionViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FileRegionSerializer
    queryset = FileRegion.objects.exclude(is_removed=True, is_user_feedback=True)
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter]
    ordering = ["-created_ts"]
    filterset_fields = ("file_id", "ml_model_id", "is_user_feedback")
    pagination_class = None

    @action(
        detail=False,
        methods=["POST"],
    )
    def mark_no_defect(self, request):
        file_id = request.data.get("file_id", None)
        ml_model_id = request.data.get("ml_model_id", None)
        if not (file_id and ml_model_id):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                FileRegion.objects.filter(file_id=file_id, ml_model_id=ml_model_id, is_user_feedback=False).update(
                    classification_correctness=False, detection_correctness=False, is_removed=True
                )
                FileRegion.objects.filter(file_id=file_id, ml_model_id=ml_model_id, is_user_feedback=True).update(
                    is_removed=True
                )
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            logging.error(e)
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["POST"])
    def update_feedback(self, request):
        file_set_filters = {}
        ml_model_filters = {}
        date__gte = datetime(2020, 7, 30, 0, 0, 0, tzinfo=pytz.UTC)
        date__lte = datetime.now(tz=pytz.UTC)
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte
        assign_defects = []
        remove_defects = []

        for key, val in request.data.items():
            if key == "feedback":
                assign_defects = val.get("assign_to_all", [])
                remove_defects = val.get("remove_from_all", [])
            elif key == "ml_model_id":
                ml_model_filters["id"] = val
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            else:
                file_set_filters[key] = val

        if not file_set_filters:
            return Response("Please specify file set filters.", status=status.HTTP_400_BAD_REQUEST)
        try:
            feedback_service = BulkFeedbackService(ml_model_id=ml_model_filters["id"])
            feedback_service.update_feedback(file_set_filters, assign_defects, remove_defects)
        except ValidationError as e:
            return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
        except NotImplementedError as e:
            return Response(e.__str__(), status=status.HTTP_400_BAD_REQUEST)
        return Response("Successfully updated feedback")


class FileRegionHistoryViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FileRegionHistorySerializer
    queryset = FileRegionHistory.objects.all()
    filter_backends = [django_filters.DjangoFilterBackend, filters.OrderingFilter]
    ordering = ["-created_ts"]
    filterset_fields = ("file_region_id", "ml_model_id", "file_id")
