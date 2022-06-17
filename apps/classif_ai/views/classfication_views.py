from datetime import datetime
from pickle import STRING
from typing import Dict
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.functions.datetime import TruncDay, TruncMonth, TruncWeek
from django.db.models.query_utils import Q

from django.http.request import HttpRequest
from apps.classif_ai.models import ModelClassification, MlModel, UseCase, FileSetInferenceQueue
from sixsense import settings

from rest_framework.decorators import action, api_view, permission_classes
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from apps.classif_ai.service import classification_service
from apps.classif_ai.serializers_.classification_view_serializers import (
    AccuracyResponse,
    AccuracyTimeseriesResponse,
    AutoClassificationDefectDistributionResponse,
    AutoClassificationResponse,
    AutoClassificationTimeseriesResponse,
    ClasswiseMetricsUseCaseLevelResponse,
    MissclassificationDefectLevelResponse,
)

import pytz

filter_params = [
    OpenApiParameter(
        name="ml_model_id__in",
        type={"type": "list"},
        location=OpenApiParameter.QUERY,
        style="form",
    ),
    OpenApiParameter(
        name="subsciption_id",
        type={"type": "list"},
        location=OpenApiParameter.QUERY,
        style="form",
    ),
    OpenApiParameter(
        name="use_case_id__in",
        type={"type": "list"},
        location=OpenApiParameter.QUERY,
        style="form",
    ),
    OpenApiParameter(
        name="date__gte",
        type=OpenApiTypes.DATE,
        location=OpenApiParameter.QUERY,
        style="form",
    ),
    OpenApiParameter(
        name="date__lte",
        type=OpenApiTypes.DATE,
        location=OpenApiParameter.QUERY,
        style="form",
    ),
    OpenApiParameter(
        name="time_format",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        style="form",
    ),
]


class ClassificationMetricsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    # TODO: Sai needs to review the code

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="auto_classification")
    def auto_classification_metrics(self, request):
        """calculates automation(auto-classification) of unit"""
        data = classification_service.auto_classification_metrics(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="auto_classification/timeseries")
    def auto_classification_metrics_timeseries(self, request):
        """calculates auto-classification of a unit in time"""
        data = classification_service.auto_classification_metrics_timeseries(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="accuracy")
    def accuracy_metrics(self, request):
        """calculates automation(auto-accuracy) of unit"""
        data = classification_service.accuracy_metrics(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="accuracy/timeseries")
    def accuracy_metrics_timseries(self, request):
        """calculates accuracy of a unit in time"""
        data = classification_service.accuracy_metrics_timeseries(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AccuracyResponse)
    @action(detail=False, methods=["get"], url_path="accuracy/defect_level")
    def accuracy_metrics_defect_level(self, request):
        """calculates performance (accuracy) of defects"""
        serializer = classification_service.accuracy_metrics_defect_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AccuracyTimeseriesResponse(many=True))
    @action(detail=False, methods=["get"], url_path="accuracy/defect_level_timeseries")
    def accuracy_metrics_defect_level_timeseries(self, request):
        """calculates performance (accuracy) of defects on the basis of time"""
        serializer = classification_service.accuracy_metrics_defect_level_timeseries(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="confusion_matrix")
    def confusion_matrix(self, request):
        """calculates confusion matrix for defects"""
        response_data = classification_service.confusion_matrix(self.get_filters(request))
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AccuracyResponse)
    @action(detail=False, methods=["get"], url_path="accuracy/wafer_level")
    def accuracy_metrics_wafer_level(self, request):
        """calculates performance (accuracy) of wafers"""
        serializer = classification_service.accuracy_metrics_wafer_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AccuracyTimeseriesResponse(many=True))
    @action(detail=False, methods=["get"], url_path="accuracy/wafer_level_timeseries")
    def accuracy_metrics_wafer_level_timeseries(self, request):
        """calculates performance (accuracy) of wafers on the basis of time"""
        serializer = classification_service.accuracy_metrics_wafer_level_timeseries(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationResponse)
    @action(detail=False, methods=["get"], url_path="auto_classification/defect_level")
    def auto_classification_metrics_defect_level(self, request):
        """calculates automation(auto-classification) of defects"""
        serializer = classification_service.auto_classification_metrics_defect_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationTimeseriesResponse(many=True))
    @action(detail=False, methods=["get"], url_path="auto_classification/defect_level_timeseries")
    def auto_classification_metrics_defect_level_timeseries(self, request):
        """calculates automation(auto-classification) of defects on the basis of time"""
        serializer = classification_service.auto_classification_metrics_defect_level_timeseries(
            self.get_filters(request)
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationDefectDistributionResponse(many=True))
    @action(detail=False, methods=["get"], url_path="auto_classification/defect_distribution")
    def auto_classification_metrics_defect_distribution(self, request):
        """calculates automation(auto-classification) of defects"""
        serializer = classification_service.auto_classification_metrics_defect_distribution(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationResponse)
    @action(detail=False, methods=["get"], url_path="auto_classification/wafer_level")
    def auto_classification_metrics_wafer_level(self, request):
        """calculates automation(auto-classification) of wafers"""
        serializer = classification_service.auto_classification_metrics_wafer_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationTimeseriesResponse(many=True))
    @action(detail=False, methods=["get"], url_path="auto_classification/wafer_level_timeseries")
    def auto_classification_metrics_wafer_level_timeseries(self, request):
        """calculates automation(auto-classification) of wafers on the basis of time"""
        serializer = classification_service.auto_classification_metrics_wafer_level_timeseries(
            self.get_filters(request)
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=MissclassificationDefectLevelResponse(many=True))
    @action(detail=False, methods=["get"], url_path="missclassification/defect_level")
    def missclassification_defect_level(self, request):
        """calculates missclassifications of defects"""
        serializer = classification_service.missclassification_defect_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="classwise/defect_level")
    def classwise_metrics_defect_level(self, request):
        """calculates automation, performance, true positives, false negatives of defects(classes)"""
        response_data = classification_service.classwise_metrics_defect_level(self.get_filters(request))
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=ClasswiseMetricsUseCaseLevelResponse(many=True))
    @action(detail=False, methods=["get"], url_path="classwise/use_case_level")
    def classwise_metrics_use_case_level(self, request):
        """calculates automation and performance distribution of usecases"""
        serializer = classification_service.classwise_metrics_use_case_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationResponse)
    @action(detail=False, methods=["get"], url_path="auto_classification/file_level")
    def auto_classification_metrics_file_level(self, request):
        """calculates automation(auto-classification) of files"""
        serializer = classification_service.auto_classification_metrics_file_level(self.get_filters(request))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationTimeseriesResponse(many=True))
    @action(detail=False, methods=["get"], url_path="auto_classification/file_level_timeseries")
    def auto_classification_metrics_file_level_timeseries(self, request):
        """calculates automation(auto-classification) of files per day"""
        serializer = classification_service.auto_classification_metrics_file_level_timeseries(
            self.get_filters(request)
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params, responses=AutoClassificationTimeseriesResponse(many=True))
    @action(detail=False, methods=["get"], url_path="auto_classification/use_case_level_timeseries")
    def auto_classification_metrics_grouped_by_use_case_timeseries(self, request):
        serializer = classification_service.auto_classification_metrics_use_case_level_timeseries(
            self.get_filters(request)
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_filters(self, request: HttpRequest) -> Dict:
        """converts into request object that services can read
        this is a temporary method, will be replaced by generic method used by all services
        added this so that services have less coupling so a future change can be easuly accommodated
        """
        file_set_filters = {}
        ml_model_filters = {}
        unit = None
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["file_set__created_ts__gte"] = date__gte
        file_set_filters["file_set__created_ts__lte"] = date__lte
        time_function = TruncDay
        # this is restricted to classification
        file_set_filters["file_set__use_case__type__in"] = ["CLASSIFICATION"]

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["model_classifications__ml_model__in"] = val.split(",")
            elif key == "ml_model_status__in":
                ml_model_filters["ml_model_status__in"] = val.split(",")
            elif key == "use_case_id__in":
                file_set_filters["file_set__use_case__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["file_set__subscription_id__in"] = val.split(",")
            elif key == "time_format":
                if val == "monthly":
                    time_function = TruncMonth
                elif val == "weekly":
                    time_function = TruncWeek
            elif key == "date__gte":
                file_set_filters["file_set__created_ts__gte"] = datetime(
                    *list(map(int, (val.split("-")))), tzinfo=pytz.UTC
                )
            elif key == "date__lte":
                file_set_filters["file_set__created_ts__lte"] = datetime(
                    *list(map(int, (val.split("-")))), tzinfo=pytz.UTC
                )
            elif key == "train_type__in":
                file_set_filters["file_set__trainingsessionfileset__dataset_train_type__in"] = val.split(",")
            elif key == "classification_type":
                file_set_filters["file_set__use_case__classification_type__in"] = val.split(",")
            elif key == "is_bookmarked":
                file_set_filters["file_set__is_bookmarked"] = bool(val)
            elif key.startswith("meta_info__"):
                file_set_filters["file_set__" + key] = val.split(",")
            elif key == "ground_truth_label__in":
                file_set_filters["gt_classifications__gt_classification_annotations__defect_id__in"] = val.split(",")
            elif key == "unit":
                unit = val
            elif key == "latest_use_case_model":
                ml_model_filters["latest_use_case_model"] = val
            elif key == "is_live":
                ml_model_filters["file_set__upload_session__is_live"] = bool(val)
            else:
                file_set_filters["file_set__" + key] = val.split(",")

        # TODO: once we support training model filter, we can remove this block
        if (
            file_set_filters.get("file_set__trainingsessionfileset__dataset_train_type__in") is not None
            and ml_model_filters.get("model_classifications__ml_model__in") is not None
        ):
            file_set_filters[
                "file_set__trainingsessionfileset__training_session__new_ml_model_id__in"
            ] = ml_model_filters.get("model_classifications__ml_model__in")

        # if no model is passed, show data of all the models selected
        if ml_model_filters.get("model_classifications__ml_model__in") is None:
            # if client wants latest deployed model,
            # then for the file, usecase is fetched, then model(filtered by model status) with highest version is pulled
            # basically, only those files are selected which belong to latest model of the usecase
            # TODO: models should have a boolean flag saying latest deployed in production or non-production, that way we won't need to sort and find first, push the efforts to write query and make read faster
            if ml_model_filters.get("latest_use_case_model"):
                # if model status is passed, then only models of these statuses should be under consideration
                status_filter = Q()
                if ml_model_filters.get("ml_model_status__in"):
                    status_filter = status_filter & Q(status__in=ml_model_filters.get("ml_model_status__in"))
                    # delete as model status filter is already applied, no need to again filter on model status
                    del ml_model_filters["ml_model_status__in"]
                use_cases = []
                if file_set_filters.get("file_set__use_case__in"):
                    use_cases = file_set_filters.get("file_set__use_case__in")
                ml_model_filters["model_classifications__ml_model__in"] = list(
                    self.get_latest_model_of_use_case(use_cases, status_filter).values()
                )
                # delete as this column is not in the model table
                del ml_model_filters["latest_use_case_model"]
            # default is assumed as pick the latest classification of the file(filtered by model status)
            # if model status is deployed_in_production or retired(was deployed in production historically)
            # then for a file we try to find the latest classification under given filters
            # this allows us to go back in time and fetch results of older productionalized model versions
            else:
                status_filter = Q()
                if ml_model_filters.get("ml_model_status__in"):
                    status_filter = status_filter & Q(ml_model__status__in=ml_model_filters.get("ml_model_status__in"))
                    # delete as model status filter is already applied, no need to again filter on model status
                    del ml_model_filters["ml_model_status__in"]
                sub_query = Subquery(
                    ModelClassification.objects.filter(Q(file=OuterRef("model_classifications__file")) & status_filter)
                    .order_by("-created_ts")
                    .values("ml_model")[:1]
                )
                ml_model_filters["model_classifications__ml_model__in"] = sub_query
        else:
            if ml_model_filters.get("ml_model_status__in"):
                ml_model_filters["model_classifications__ml_model__status__in"] = ml_model_filters.get(
                    "ml_model_status__in"
                )
                del ml_model_filters["ml_model_status__in"]

        if ml_model_filters.get("latest_use_case_model"):
            del ml_model_filters["latest_use_case_model"]

        return {
            "file_set_filters": file_set_filters,
            "ml_model_filters": ml_model_filters,
            "time_function": time_function,
            "unit": unit,
        }

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="distribution/use_case_level")
    def distribution_metrics_use_case(self, request):
        data = classification_service.distribution_metrics_use_case(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="distribution/folder_level")
    def distribution_metrics_folder_level(self, request):
        data = classification_service.distribution_metrics_folder_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="distribution/defect_level")
    def distribution_metrics_defect_level(self, request):
        data = classification_service.classwise_metrics_defect_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="distribution/wafer_level")
    def distribution_metrics_wafer_level(self, request):
        data = classification_service.distribution_metrics_wafer_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="cohort/use_case_level")
    def cohort_metrics_use_case_level(self, request):
        """calculates cohort metrics on use case"""
        data = classification_service.cohort_metrics_use_case_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="cohort/defect_level")
    def cohort_metrics_defect_level(self, request):
        """calculates cohort metrics on defect"""
        data = classification_service.cohort_metrics_defect_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="cohort/folder_level")
    def cohort_metrics_folder_level(self, request):
        """calculates cohort metrics on folders"""
        data = classification_service.cohort_metrics_folder_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["get"], url_path="cohort/wafer_level")
    def cohort_metrics_wafer_level(self, request):
        """calculates cohort metrics on wafers"""
        data = classification_service.cohort_metrics_wafer_level(self.get_filters(request))
        return Response(data, status=status.HTTP_200_OK)

    def get_latest_model_of_use_case(self, use_cases, status_filter):
        # if no usecases are sent, assume all usecase are needed
        use_case_id_in = Q()
        if use_cases:
            use_case_id_in = Q(id__in=use_cases)
        model_latest = MlModel.objects.filter(Q(use_case=OuterRef("id")) & status_filter).order_by("-version")
        result = (
            UseCase.objects.filter(use_case_id_in)
            .annotate(ml_model_id=Subquery(model_latest.values("id")[:1]))
            .values("id", "ml_model_id")
        )
        return {row.get("id"): row.get("ml_model_id") for row in result if row.get("ml_model_id")}
