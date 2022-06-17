from rest_framework import permissions, mixins
from rest_framework.viewsets import GenericViewSet
from django_filters import rest_framework as django_filters

from apps.classif_ai.filters import MLModelClassificationFilterSet, MLModelDetectionFilterSet
from apps.classif_ai.models import ModelClassification, ModelDetection
from apps.classif_ai.serializers import MLModelClassificationSerializer, MLModelDetectionSerializer

# TODO Test cases are pending to implement
class MLModelClassificationViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ModelClassification.objects.all()
    serializer_class = MLModelClassificationSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = MLModelClassificationFilterSet


# TODO Test cases are pending to implement
class MLModelDetectionViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ModelDetection.objects.all()
    serializer_class = MLModelDetectionSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = MLModelDetectionFilterSet
