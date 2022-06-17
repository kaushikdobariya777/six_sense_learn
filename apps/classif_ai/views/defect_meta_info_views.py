from rest_framework import permissions, filters

from apps.classif_ai.models import DefectMetaInfo
from apps.classif_ai.serializers import DefectMetaInfoSerializer
from common.views import BaseViewSet


class DefectMetaInfoViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DefectMetaInfoSerializer
    queryset = DefectMetaInfo.objects.all()
    pagination_class = None
    filter_backends = [filters.OrderingFilter]
    ordering = ["-updated_ts"]
