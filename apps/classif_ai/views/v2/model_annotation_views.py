from django_filters import rest_framework as django_filters
from rest_framework import mixins, permissions
from rest_framework.permissions import IsAdminUser, IsAuthenticated, BasePermission
from rest_framework.viewsets import GenericViewSet

from apps.classif_ai.filters import MLModelClassificationFilterSet, MLModelDetectionFilterSet
from apps.classif_ai.models import ModelClassification, ModelDetection
from apps.classif_ai.serializer.model_annotation_serializers import (
    MLModelClassificationSerializer,
    MLModelDetectionSerializer,
)


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class MLModelClassificationViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet
):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ModelClassification.objects.all()
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = MLModelClassificationFilterSet
    serializer_class = MLModelClassificationSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsSuperUser()]
        else:
            return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(
            {
                "defects": self.request.data.get("defects", None),
            }
        )
        return context


class MLModelDetectionViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet
):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ModelDetection.objects.all()
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = MLModelDetectionFilterSet
    serializer_class = MLModelDetectionSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsSuperUser()]
        else:
            return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(
            {
                "detection_regions": self.request.data.get("detection_regions", None),
            }
        )
        return context
