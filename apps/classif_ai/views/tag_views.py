from rest_framework import permissions, filters

from apps.classif_ai.models import Tag
from apps.classif_ai.serializers import TagSerializer
from common.views import BaseViewSet


class TagViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TagSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ["-id"]
    queryset = Tag.objects.all()
