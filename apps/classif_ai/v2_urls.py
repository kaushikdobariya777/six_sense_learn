from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.classif_ai.views.v2 import model_annotation_views

default_router = DefaultRouter()

default_router.register(
    r"ml-model-classification",
    model_annotation_views.MLModelClassificationViewSet,
    basename="ml-model-classification-v2",
)
default_router.register(
    r"ml-model-detection",
    model_annotation_views.MLModelDetectionViewSet,
    basename="ml-model-detection-v2",
)


urlpatterns = [
    path("", include(default_router.urls)),
]
