from rest_framework import permissions, filters

from apps.classif_ai.models import UseCaseDefect
from apps.classif_ai.serializers import UseCaseDefectSerializer
from common.views import BaseViewSet


class UseCaseDefectViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UseCaseDefectSerializer
    queryset = UseCaseDefect.objects.all()
    pagination_class = None
    filter_backends = [filters.OrderingFilter]
    ordering = ["-id"]
