from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.classif_ai.views import (
    classfication_views,
    detection_views,
    file_set_views,
    task_result_views,
    use_case_defect_views,
    defect_meta_info_views,
    defect_views,
    training_session_views,
    metrics_views,
    file_region_views,
    upload_session_views,
    ml_model_views,
    file_set_inference_queue_views,
    use_case_views,
    training_session_file_set_views,
    user_defect_views,
    wafer_map_views,
    ml_model_defect_views,
    tag_views,
)
from common.routers import GETPOSTRouter, ReadOnlyRouter

get_post_router = GETPOSTRouter()
default_router = DefaultRouter()
read_only_router = ReadOnlyRouter()
default_router.register(r"file-set", file_set_views.FileSetViewSet, basename="file-set")
default_router.register(r"upload-session", upload_session_views.UploadSessionViewSet, basename="upload-session")
default_router.register(r"file-region", file_region_views.FileRegionViewSet, basename="file-region")
read_only_router.register(r"application-charts", metrics_views.ApplicationChartsViewSet, basename="application-charts")
read_only_router.register(
    r"data-performance-summary", metrics_views.PerformanceSummaryViewSet, basename="data-performance-summary"
)
default_router.register(
    r"training-session", training_session_views.TrainingSessionViewSet, basename="training-session"
)
default_router.register(r"defects", defect_views.DefectsViewSet, basename="defects")
default_router.register(r"defect-meta-info", defect_meta_info_views.DefectMetaInfoViewSet, basename="defect-meta-info")
default_router.register(r"use-case-defects", use_case_defect_views.UseCaseDefectViewSet, basename="use-case-defects")
default_router.register(r"ml-model", ml_model_views.MlModelViewSet, basename="ml-models")
default_router.register(r"use-case", use_case_views.UseCaseViewSet, basename="use-case")
default_router.register(
    r"user-classification",
    user_defect_views.UserClassificationViewSet,
    basename="user-classification",
)
default_router.register(
    r"user-detection",
    user_defect_views.UserDetectionViewSet,
    basename="user-detection",
)
read_only_router.register(
    r"ml-model-classification",
    ml_model_defect_views.MLModelClassificationViewSet,
    basename="ml-model-classification",
)
read_only_router.register(
    r"ml-model-detection",
    ml_model_defect_views.MLModelDetectionViewSet,
    basename="ml-model-detection",
)
default_router.register(
    r"file-set-inference-queue",
    file_set_inference_queue_views.FileSetInferenceQueueViewSet,
    basename="file-set-inference-queue",
)
get_post_router.register(
    r"classification/metrics", classfication_views.ClassificationMetricsViewSet, basename="classification-metrics"
)
get_post_router.register(r"detection", detection_views.DetectionViewSet, basename="detection")
default_router.register(r"wafer-map", wafer_map_views.WaferMapViewSet, basename="wafer-map")
default_router.register(r"tags", tag_views.TagViewSet, basename="tags")
default_router.register(
    r"training-session-file-sets",
    training_session_file_set_views.TrainingSessionFileSetViewSet,
    basename="training-session-file-sets",
)
default_router.register(r"tasks", task_result_views.TaskResultViewSet, basename="tasks")

urlpatterns = [
    path("", include(get_post_router.urls)),
    path("", include(default_router.urls)),
    path("", include(read_only_router.urls)),
    path("file-region-history", file_region_views.FileRegionHistoryViewSet.as_view({"get": "list"})),
    # path('file-set-inference-queue', file_set_inference_queue_views.FileSetInferenceQueueViewSet.as_view({'post': 'create', 'get': 'list'})),
    path("file-set-meta-info/<str:field>/distinct", file_set_views.file_set_meta_info_distinct_values),
    # path('defects', views.DefectsViewSet.as_view({'post': 'create', 'get': 'list'})),
    # path('defects/<int:pk>', views.DefectsViewSet.as_view({'patch': 'partial_update'})),
    # path('use-case-defects', views.UseCaseDefectViewSet.as_view({'post': 'create', 'get': 'list'})),
    # path('use-case-defects/<int:pk>', views.UseCaseDefectViewSet.as_view({'patch': 'partial_update'})),
    # path('defect-meta-info', views.DefectMetaInfoViewSet.as_view({'post': 'create', 'get': 'list'})),
    path("data-performance-summary", metrics_views.PerformanceSummaryViewSet.as_view({"get": "list"})),
    # path('data-performance-summary', views.PerformanceSummaryViewSet.as_view({'get': 'list'})),
    path("detailed-report", metrics_views.DetailedReportViewSet.as_view({"get": "list"})),
    path("class-wise-matrix", metrics_views.ClassWiseMatrix.as_view({"get": "list"})),
    path("upload-meta-info", file_set_views.UploadMetaInfoViewSet.as_view({"patch": "partial_update"})),
    path("prediction-csv", metrics_views.prediction_csv),
    path("ai-results-csv", metrics_views.ai_results_csv),
]
