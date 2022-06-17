from django.db import connection
from django.db.models import ProtectedError, F
from django.db.models.aggregates import Count
from django_filters import rest_framework as django_filters
from rest_framework import permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.classif_ai.filters import DefectFilterSet
from apps.classif_ai.models import Defect, DefectMetaInfo, FileRegion, File
from apps.classif_ai.serializers import DefectSerializer, DefectDetailedSerializer, DefectMetaInfoSerializer
from common.views import BaseViewSet


class DefectsViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    # serializer_class = DefectDetailedSerializer
    queryset = Defect.objects.all()
    # pagination_class = None
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    ordering = ["-id"]
    # filterset_fields = ('ml_models', 'use_cases', 'subscription_id')
    filter_class = DefectFilterSet

    def get_serializer_class(self):
        if self.action == "list":
            return DefectSerializer
        return DefectDetailedSerializer

    @action(methods=["GET"], detail=False)
    def detailed(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DefectDetailedSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DefectDetailedSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=["GET", "POST"], detail=True)
    def meta_info(self, request, pk):
        if request.method == "GET":
            defect_meta_info = DefectMetaInfo.objects.filter(defect_id=pk)
            serializer = DefectMetaInfoSerializer(defect_meta_info, many=True, context={"request": request})
            return Response(serializer.data)
        elif request.method == "POST":
            # defect_meta_info = DefectMetaInfo.objects.create(defect_id=pk, **request.data)
            # serializer = DefectMetaInfoSerializer(defect_meta_info, context={"request": request})
            data = request.data
            data["defect"] = pk
            serializer = DefectMetaInfoSerializer(data=data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        region_count = FileRegion.objects.filter(defects__has_key=str(instance.id)).count()
        if region_count > 0:
            raise ProtectedError("Cannot remove defect because it has associations with images", None)
        super().perform_destroy(instance)

    @action(methods=["GET"], detail=False)
    def gt_instance_counts(self, request):
        defects = DefectFilterSet(request.query_params, queryset=Defect.objects.all(), request=request)
        defect_instances = (
            defects.qs.annotate(gt_defects=F("gt_classification_defects"))
            .values("id", "name")
            .annotate(total_instances=Count("gt_defects"))
        )
        return Response(defect_instances)
