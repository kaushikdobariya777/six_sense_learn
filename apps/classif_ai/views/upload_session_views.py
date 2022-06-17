from django.db import transaction, connection
from django.db.models import Q
from django.db.models.aggregates import Count
from django_filters import rest_framework as django_filters
from rest_framework import permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.classif_ai.filters import UploadSessionFilterSet
from apps.classif_ai.models import UploadSession, FileSet, FileSetInferenceQueue, File, FileRegion, FileRegionHistory
from apps.classif_ai.serializers import UploadSessionSerializer
from apps.classif_ai.tasks import stitch_image_worker
from common.views import BaseViewSet
from sixsense.settings import PROJECT_START_DATE

from datetime import datetime
import pytz


class UploadSessionViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = UploadSession.objects.all()
    serializer_class = UploadSessionSerializer
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filter_class = UploadSessionFilterSet
    ordering = ["-is_live", "-created_ts"]
    ordering_fields = ["name"]

    # filterset_fields = ('id', 'name', 'subscription_id')

    @action(
        detail=False,
        methods=["GET"],
    )
    def distinct(self, request):
        created_ts__gte = PROJECT_START_DATE
        created_ts__lte = datetime.now(tz=pytz.UTC)

        for key, val in request.query_params.items():
            if key == "date__gte":
                created_ts__gte = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                created_ts__lte = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)

        queryset = self.filter_queryset(self.get_queryset())
        result = (
            queryset.values("id", "name")
            .order_by("-is_live", "-created_ts")
            .annotate(
                file_set_count=Count(
                    "file_sets", filter=Q(created_ts__gte=created_ts__gte, created_ts__lte=created_ts__lte)
                )
            )
        )
        # page = self.paginate_queryset(queryset)
        # if page is not None:
        #     serializer = DefectDetailedSerializer(page, many=True)
        #     return self.get_paginated_response(serializer.data)
        # serializer = DefectDetailedSerializer(queryset, many=True)
        # return Response(serializer.data)
        # subscription_id = request.query_params.get('subscription_id', None)
        # result = UploadSession.objects.filter(
        #     subscription_id=subscription_id).values('id', 'name').order_by('-is_live', '-created_ts')
        return Response({"data": result}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        with transaction.atomic():
            file_sets = FileSet.objects.filter(upload_session=instance)
            file_set_inference_queues = FileSetInferenceQueue.objects.filter(file_set__in=file_sets)
            files = File.objects.filter(file_set__in=file_sets)
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
            # Training Session File Sets not deletion is intentional.
            # If a file set contains training session file set, then it will throw an error when trying to delete file
            # sets. We don't want to delete the filesets which are used for training
            file_sets.delete()
            instance.delete()

    @action(detail=True, methods=["POST"])
    def stitch_images(self, request, pk):
        stitch_image_worker.delay(upload_session_id=pk, schema=connection.schema_name)
        return Response(
            {"success": True, "message": "A new folder will soon be created with the stitched images"},
            status=status.HTTP_200_OK,
        )
