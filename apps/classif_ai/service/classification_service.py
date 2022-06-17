from typing import Dict, List
from django.contrib.postgres.fields.citext import CITextField
from rest_framework.exceptions import ValidationError
from django.db.models.expressions import F
from django.db.models.fields import DateField, FloatField, CharField
from django.db.models import Case, Value, When, Count
from django.db.models.functions.comparison import Cast, Coalesce
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q, FilteredRelation
from apps.classif_ai.models import File, UseCase
from apps.classif_ai.service.metrics_service import (
    ClasswiseMetrics,
    CommonMetrics,
    ConfusionMatrix,
    AccuracyMetrics,
    AutoClassificationMetrics,
    DistributionMetrics,
)
from apps.classif_ai.helpers import build_query

from apps.classif_ai.serializers_.classification_view_serializers import (
    AccuracyResponse,
    AccuracyTimeseriesResponse,
    AutoClassificationDefectDistributionResponse,
    AutoClassificationResponse,
    AutoClassificationTimeseriesResponse,
    ClasswiseMetricsDefectLevelResponse,
    ClasswiseMetricsUseCaseLevelResponse,
    MissclassificationDefectLevelResponse,
    UseCaseAutoClassificationTimeSeriesResponse,
)

### modularity or speed ?
# to maintain MODULARITY, data retrieval and data calculation can be separated
# service classes aim to get data whereas metrics classes use the obtained data to calculate metrics
# could be particularly helpful in cases where same data could be used for multiple calculation

# we could go for SPEEDY results by letting sql do the calculation so we directly get the metrics
# metrics classes could do the complex sql and service classes could simply be a mediator

# We are proceeding with MODULARITY!

### why the static methods?
# no benefit of creating metrics object, hence the static method call
# we create a object so that it can be reused in the code
# but chances that same metric type will be asked in single API call is very low
# and using same object across multiple API call(shared resources) is risky

# TODO: classwise metrics and wafer level metrics should work multi-label


def confident_data(request: Dict) -> QuerySet:
    """[gets data with confidence higher than the threshold set]"""
    # TODO: change the name to file_filters
    file_filter = build_query(request.get("file_set_filters"))
    ml_model_filter = build_query(request.get("ml_model_filters"))

    return File.objects.filter(  # multiple where clauses on same table should be in same filter, otherwise multiple joins are created
        Q(
            model_classifications__ml_model__confidence_threshold__lte=F(
                "model_classifications__model_classification_annotations__confidence"
            )
        )
        & file_filter
        & ml_model_filter
        & Q(gt_classifications__gt_classification_annotations__isnull=False)
    )


def filtered_data(request: Dict, is_gt=True) -> QuerySet:
    """[gets data that are auto classified by ai]"""

    file_filter = build_query(request.get("file_set_filters"))
    ml_model_filter = build_query(request.get("ml_model_filters"))

    gt_filter = Q()
    if is_gt:
        gt_filter = Q(gt_classifications__gt_classification_annotations__isnull=False)

    return File.objects.filter(  # multiple where clauses on same table should be in same filter, otherwise multiple joins are created
        file_filter & ml_model_filter & gt_filter
    )


def confusion_matrix(request: Dict) -> Dict:
    """creates confusion matrix for defects"""
    file_filter = build_query(request.get("file_set_filters"))
    ml_model_filter = build_query(request.get("ml_model_filters"))

    use_case_id = request.get("file_set_filters").get("file_set__use_case__in")
    if use_case_id is None or len(use_case_id) != 1:
        raise ValidationError("confusion matrix needs one usecase")
    retrieved_use_case = UseCase.objects.filter(id=use_case_id[0]).first()
    if retrieved_use_case is None:
        raise ValidationError("use case does not exist")
    if retrieved_use_case.classification_type != "SINGLE_LABEL" or retrieved_use_case.type != "CLASSIFICATION":
        raise ValidationError("confusion matrix needs single label classification data")

    # this filter excludes the files with model_defect = null or gt_defect = null
    # if we want those files in confusion matrix, just replace following filter with Q()
    exclude_null_defects = Q(
        joined__defect__isnull=False, gt_classifications__gt_classification_annotations__defect__isnull=False
    )

    input_queryset = (
        File.objects.annotate(
            joined=FilteredRelation(  # left join
                "model_classifications__model_classification_annotations",
            )
        )
        .filter(  # multiple where clauses on same table should be in same filter, otherwise multiple joins are created
            Q(model_classifications__isnull=False)
            & Q(gt_classifications__isnull=False)
            & Q(model_classifications__ml_model__isnull=False)
            & ml_model_filter
            & file_filter
            & exclude_null_defects
        )
        .values("joined")
        .annotate(
            model_name=F("model_classifications__ml_model__name"),
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            model_defect_id=Case(
                When(
                    model_classifications__ml_model__confidence_threshold__lte=F("joined__confidence"),
                    then=F("joined__defect__id"),
                ),
                default=Value(-1),
            ),
            gt_defect_name=F("gt_classifications__gt_classification_annotations__defect__name"),
            gt_defect_organization_code=Coalesce(
                F("gt_classifications__gt_classification_annotations__defect__organization_defect_code"), Value("N/A")
            ),
            model_defect_organization_code=Case(
                When(
                    model_classifications__ml_model__confidence_threshold__lte=F("joined__confidence"),
                    then=F("joined__defect__organization_defect_code"),
                ),
                default=Value("N/A", output_field=CharField()),
            ),
            model_defect_name=Case(
                When(
                    model_classifications__ml_model__confidence_threshold__lte=F("joined__confidence"),
                    then=F("joined__defect__name"),
                ),
                default=Value("Unknown", output_field=CITextField()),
            ),
            fileset_id=F("file_set_id"),
            defect_confidence=F("joined__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
        )
        .values(
            "file_id",
            "gt_defect_id",
            "model_defect_id",
            "gt_defect_name",
            "model_defect_name",
            "fileset_id",
            "gt_defect_organization_code",
            "model_defect_organization_code",
            "model_name",
            "defect_confidence",
            "confidence_threshold",
        )
    )
    return ConfusionMatrix.confusion_matrix(input_queryset)


def accuracy_metrics_defect_level(request: Dict) -> AccuracyResponse:
    """[gets accuracy of AI on defects]"""
    input_queryset = (
        confident_data(request)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
        )
        .values("file_id", "gt_defect_id", "model_defect_id")
    )
    return AccuracyResponse(AccuracyMetrics.defect_level(input_queryset))


def accuracy_metrics_defect_level_timeseries(request: Dict) -> AccuracyTimeseriesResponse:
    """[gets timeseries of accuracy of AI on defects]"""
    time_function = request.get("time_function")
    input_queryset = confident_data(request).annotate(
        file_id=F("id"),
        gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
        model_defect_id=F("model_classifications__model_classification_annotations__defect"),
        effective_date=Cast(
            time_function("created_ts"),
            DateField(),
        ),
    )
    # queryset sent for metrics calculation
    return AccuracyTimeseriesResponse(AccuracyMetrics.defect_level_timeseries(input_queryset), many=True)


def accuracy_metrics_wafer_level(request: Dict) -> AccuracyResponse:
    """[gets accuracy of AI on wafers]"""
    # data preparation

    input_queryset = (
        confident_data(request)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
            wafer_id=F("file_set__wafer__id"),
            wafer_threshold=Cast(
                F("file_set__use_case__automation_conditions__threshold_percentage"),
                output_field=FloatField(),
            ),
        )
        .values("file_id", "gt_defect_id", "model_defect_id", "wafer_id", "wafer_threshold")
    )
    # queryset sent for metrics calculation
    return AccuracyResponse(AccuracyMetrics.wafer_level(input_queryset))


def accuracy_metrics_wafer_level_timeseries(request: Dict) -> AccuracyTimeseriesResponse:
    """[gets accuracy of AI on wafers in timeseries manner]"""
    # data preparation
    # we can also add usecases and wafers in filter clause
    time_function = request.get("time_function")
    input_queryset = (
        confident_data(request)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
            wafer_id=F("file_set__wafer__id"),
            wafer_threshold=Cast(
                F("file_set__use_case__automation_conditions__threshold_percentage"),
                output_field=FloatField(),
            ),
            effective_date=Cast(
                time_function("created_ts"),
                DateField(),
            ),
        )
        .values("file_id", "gt_defect_id", "model_defect_id", "wafer_id", "wafer_threshold", "effective_date")
    )
    # queryset sent for metrics calculation
    return AccuracyTimeseriesResponse(AccuracyMetrics.wafer_level_timeseries(input_queryset), many=True)


def auto_classification_metrics_defect_level(request: Dict) -> AutoClassificationResponse:
    """[gets autoclassification metrics of AI on defects]"""
    input_queryset = (
        filtered_data(request)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
        )
        .values("file_id", "gt_defect_id", "confidence", "confidence_threshold")
    )
    # queryset sent for metrics calculation
    return AutoClassificationResponse(AutoClassificationMetrics.defect_level(input_queryset))


def auto_classification_metrics_defect_level_timeseries(request: Dict) -> AutoClassificationTimeseriesResponse:
    """[gets timeseries of autoclassification of AI on defects]"""
    time_function = request.get("time_function")
    input_queryset = filtered_data(request).annotate(
        file_id=F("id"),
        gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
        confidence=F("model_classifications__model_classification_annotations__confidence"),
        confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
        effective_date=Cast(
            time_function("created_ts"),
            DateField(),
        ),
    )
    # queryset sent for metrics calculation
    return AutoClassificationTimeseriesResponse(
        AutoClassificationMetrics.defect_level_timeseries(input_queryset), many=True
    )


def auto_classification_metrics_defect_distribution(request: Dict) -> AutoClassificationDefectDistributionResponse:
    """[gets defect distribution of auto_classification metrics of AI on defects]"""
    input_queryset = filtered_data(request).annotate(
        file_id=F("id"),
        gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
        confidence=F("model_classifications__model_classification_annotations__confidence"),
        confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
    )
    return AutoClassificationDefectDistributionResponse(
        AutoClassificationMetrics.defect_distribution(input_queryset), many=True
    )


def auto_classification_metrics_wafer_level(request: Dict) -> AutoClassificationResponse:
    """[gets autoclassification of AI on wafers]"""
    input_queryset = (
        filtered_data(request, is_gt=False)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            wafer_id=F("file_set__wafer__id"),
            wafer_status=F("file_set__wafer__status"),
            wafer_threshold=Cast(
                F("file_set__use_case__automation_conditions__threshold_percentage"),
                output_field=FloatField(),
            ),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
        )
        .values(
            "file_id",
            "gt_defect_id",
            "wafer_id",
            "wafer_status",
            "wafer_threshold",
            "confidence",
            "confidence_threshold",
        )
    )
    return AutoClassificationResponse(AutoClassificationMetrics.wafer_level(input_queryset))


def auto_classification_metrics_wafer_level_timeseries(request: Dict) -> AutoClassificationTimeseriesResponse:
    """[gets autoclassification of AI on wafers in timeseries manner]"""
    time_function = request.get("time_function")
    input_queryset = (
        filtered_data(request, is_gt=False)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            wafer_id=F("file_set__wafer__id"),
            wafer_threshold=Cast(
                F("file_set__use_case__automation_conditions__threshold_percentage"),
                output_field=FloatField(),
            ),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
            effective_date=Cast(
                time_function("created_ts"),
                DateField(),
            ),
        )
        .values(
            "file_id",
            "gt_defect_id",
            "wafer_id",
            "wafer_threshold",
            "confidence",
            "confidence_threshold",
            "effective_date",
        )
    )
    return AutoClassificationTimeseriesResponse(
        AutoClassificationMetrics.wafer_level_timeseries(input_queryset), many=True
    )


def missclassification_defect_level(request: Dict) -> MissclassificationDefectLevelResponse:
    input_queryset = (
        confident_data(request)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            gt_defect_name=F("gt_classifications__gt_classification_annotations__defect__name"),
            model_defect_name=F("model_classifications__model_classification_annotations__defect__name"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
        )
        .values("file_id", "gt_defect_id", "model_defect_id", "gt_defect_name", "model_defect_name")
    )
    return MissclassificationDefectLevelResponse(
        CommonMetrics.missclassification_defect_level(input_queryset), many=True
    )


def classwise_metrics_defect_level(request: Dict) -> ClasswiseMetricsDefectLevelResponse:
    input_queryset = get_query_set(request)
    return ClasswiseMetricsDefectLevelResponse(ClasswiseMetrics.defect_level(input_queryset), many=True).data[:]


def classwise_metrics_use_case_level(request: Dict) -> ClasswiseMetricsUseCaseLevelResponse:
    input_queryset = (
        filtered_data(request)
        .annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
            model_defect_name=F("model_classifications__model_classification_annotations__defect__name"),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
            use_case_id=F("file_set__use_case_id"),
            use_case_name=F("file_set__use_case__name"),
        )
        .values(
            "file_id",
            "gt_defect_id",
            "model_defect_id",
            "confidence",
            "confidence_threshold",
            "use_case_id",
            "use_case_name",
        )
    )
    return ClasswiseMetricsUseCaseLevelResponse(ClasswiseMetrics.use_case_level(input_queryset), many=True)


def auto_classification_metrics_file_level(request: Dict) -> AutoClassificationResponse:
    """[gets autoclassification metrics of AI on file, if a file has atleast one confident defect, that file is auto-classified]"""
    input_queryset = (
        filtered_data(request, is_gt=False)
        .annotate(
            file_id=F("id"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect"),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
        )
        .values("file_id", "model_defect_id", "confidence", "confidence_threshold")
    )
    # queryset sent for metrics calculation
    return AutoClassificationResponse(AutoClassificationMetrics.file_level(input_queryset))


def auto_classification_metrics_file_level_timeseries(request: Dict) -> AutoClassificationTimeseriesResponse:
    """[gets autoclassification metrics of AI on file, if a file has atleast one confident defect, that file is auto-classified]"""
    time_function = request.get("time_function")
    input_queryset = (
        filtered_data(request, is_gt=False)
        .annotate(
            file_id=F("id"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect"),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
            effective_date=Cast(
                time_function("created_ts"),
                DateField(),
            ),
        )
        .values("file_id", "model_defect_id", "confidence", "confidence_threshold", "effective_date")
    )
    # queryset sent for metrics calculation
    return AutoClassificationTimeseriesResponse(
        AutoClassificationMetrics.file_level_timeseries(input_queryset), many=True
    )


def auto_classification_metrics_use_case_level_timeseries(request: Dict):
    distribution = None
    if request.get("unit") == "wafer":
        distribution = auto_classification_metrics_use_case_on_wafer_timeseries(request)
    elif request.get("unit") == "file":
        distribution = auto_classification_metrics_use_case_on_file_timeseries(request)
    else:
        raise ValidationError("this unit is not accepted")
    return distribution


def auto_classification_metrics_use_case_on_wafer_timeseries(
    request: Dict,
) -> UseCaseAutoClassificationTimeSeriesResponse:
    input_queryset = get_query_set(request)
    use_case_wafer_data = DistributionMetrics.file_distribution(
        input_queryset,
        group_by=["use_case_id", "wafer_id", "wafer_threshold", "effective_date"],
        order_by=["use_case_id", "effective_date"],
    )
    use_case_wafer_data = use_case_wafer_data.values(
        "use_case_id", "wafer_id", "wafer_threshold", "effective_date", "auto_classified_percentage"
    )
    use_case_data = DistributionMetrics.use_case_on_wafer_timeseries(use_case_wafer_data)
    return use_case_level_timeseries_response(use_case_data)


def auto_classification_metrics_use_case_on_file_timeseries(
    request: Dict,
) -> UseCaseAutoClassificationTimeSeriesResponse:
    input_queryset = get_query_set(request)
    use_case_data = DistributionMetrics.file_distribution(
        input_queryset, group_by=["use_case_id", "effective_date"], order_by=["use_case_id", "effective_date"]
    )
    use_case_data = use_case_data.values(
        "use_case_id", "effective_date", "total", "auto_classified", "auto_classified_percentage"
    )
    return use_case_level_timeseries_response(use_case_data)


def use_case_level_timeseries_response(input_data):
    response = []
    use_case_id = None
    data = {}
    for el in input_data:
        if el["use_case_id"] != use_case_id:
            if data:
                response.append(data)
            use_case_id = el["use_case_id"]
            data = {"use_case_id": use_case_id, "time_series_data": []}
        data["time_series_data"].append(
            {
                "effective_date": el["effective_date"],
                "percentage": el["auto_classified_percentage"],
                "auto_classified": el["auto_classified"],
                "manual": el["total"] - el["auto_classified"],
                "total": el["total"],
            }
        )
    if data:
        response.append(data)
    return UseCaseAutoClassificationTimeSeriesResponse(response, many=True)


def distribution_metrics_use_case(request: Dict):
    """
    returns distribution of usecase based on the unit passed,
    units accepted are wafer and file,
    if no unit is passed, wafer is assumed. This was done after the decision that we dont need unit=image for this metrics on the ui
    TODO: change this default behaviour, basically raise error when unit is none
    """
    distribution = None
    if request.get("unit") == "wafer" or request.get("unit") is None:
        distribution = distribution_metrics_use_case_on_wafer(request)
    elif request.get("unit") == "file":
        distribution = distribution_metrics_use_case_on_file(request)
    else:
        raise ValidationError("this unit is not accepted")
    return distribution


def distribution_metrics_use_case_on_wafer(request):
    input_queryset = get_query_set(request)
    main_distribution = DistributionMetrics.file_distribution(
        input_queryset,
        group_by=["use_case_id", "use_case_name", "ml_model_id", "ml_model_name", "wafer_id", "wafer_threshold"],
    )
    distribution = DistributionMetrics.use_case_on_wafer(main_distribution)
    return distribution


def distribution_metrics_use_case_on_file(request):
    input_queryset = get_query_set(request)
    distribution = DistributionMetrics.file_distribution(
        input_queryset,
        group_by=["use_case_id", "use_case_name", "ml_model_id", "ml_model_name"],
        order_by=["accuracy_percentage"],
        order="asc",
    )
    return distribution


def distribution_metrics_folder_level(request: Dict):
    input_queryset = get_query_set(request)
    distribution = DistributionMetrics.file_distribution(
        input_queryset, group_by=["upload_session_id", "upload_session_name"]
    )
    return distribution


def distribution_metrics_defect_level(request: Dict):
    input_queryset = get_query_set(
        request, additional_filters=[Q(gt_classifications__gt_classification_annotations__isnull=False)]
    )
    distribution = DistributionMetrics.file_distribution(input_queryset, group_by=["gt_defect_id", "gt_defect_name"])
    return distribution


def distribution_metrics_wafer_level(request: Dict):
    input_queryset = get_query_set(request)
    distribution = DistributionMetrics.file_distribution(
        input_queryset, group_by=["wafer_id", "organization_wafer_id", "wafer_status", "wafer_created_ts"]
    )
    return distribution


def cohort_metrics_defect_level(request: Dict):
    # TODO: below commented was the ideal way but defect metrics needs different columns as output and cohorts are not deigned on these new columns, hence so much efforts, need to work on these in future
    # condition, cohorts = cohort_condition_creation(request)
    # distribution = distribution_metrics_defect_level(request)
    # defect_distribution = distribution.query.sql_with_params()
    # distribution = DistributionMetrics.cohort_metrics(*defect_distribution, condition, "gt_defect_id")
    # return cohort_response(cohorts, distribution)
    accuracy_ranges_list = request.get("file_set_filters").get("file_set__accuracy")
    if accuracy_ranges_list is not None:
        del request.get("file_set_filters")["file_set__accuracy"]
    else:
        raise ValidationError("auto_classification or accuracy ranges are not present")
    input_queryset = get_query_set(request)
    distribution = ClasswiseMetrics.defect_level(input_queryset)
    cohorts = {}
    overall_count = 0
    for index in range(0, len(accuracy_ranges_list) - 1):
        cohort = accuracy_ranges_list[index] + "-" + accuracy_ranges_list[index + 1]
        cohorts[cohort] = {"cohort": cohort, "total": 0, "gt_defect_ids": set(), "percentage": None}
    for row in distribution:
        for index in range(0, len(accuracy_ranges_list) - 1):
            cohort = accuracy_ranges_list[index] + "-" + accuracy_ranges_list[index + 1]
            if row.get("recall_percentage") is None:
                cohort = "N/A"
                if cohorts.get(cohort) is None:
                    cohorts[cohort] = {"cohort": cohort, "total": 0, "gt_defect_ids": set(), "percentage": None}
                overall_count = overall_count + 1
                cohorts[cohort]["total"] = cohorts[cohort].get("total") + 1
                defects = cohorts[cohort].get("gt_defect_ids")
                defects.add(row.get("gt_defect_id"))
                cohorts[cohort]["gt_defect_ids"] = defects
                break
            elif row.get("recall_percentage") >= int(accuracy_ranges_list[index]) and (
                row.get("recall_percentage") <= int(accuracy_ranges_list[index + 1])
                if index + 1 == len(accuracy_ranges_list) - 1
                else row.get("recall_percentage") < int(accuracy_ranges_list[index + 1])
            ):
                overall_count = overall_count + 1
                cohorts[cohort]["total"] = cohorts[cohort].get("total") + 1
                defects = cohorts[cohort].get("gt_defect_ids")
                defects.add(row.get("gt_defect_id"))
                cohorts[cohort]["gt_defect_ids"] = defects
                break

    null_cohort = None
    for cohort in cohorts:
        if overall_count > 0:
            cohorts[cohort]["percentage"] = 100 * cohorts[cohort].get("total") / overall_count
        else:
            # TODO: remove this else block, if total is zero, percentage should be null.
            # doing this for now as UI will break as it has not handled null
            cohorts[cohort]["percentage"] = 0
    if cohorts.get("N/A"):
        null_cohort = cohorts.get("N/A")
        del cohorts["N/A"]
    cohort_response = list(cohorts.values())[::-1]
    if null_cohort:
        cohort_response.append(null_cohort)
    return cohort_response


def cohort_metrics_folder_level(request: Dict):
    condition, cohorts = cohort_condition_creation(request)
    distribution = distribution_metrics_folder_level(request)
    if distribution:
        upload_session_distribution = distribution.query.sql_with_params()
        distribution = DistributionMetrics.cohort_metrics(*upload_session_distribution, condition, "upload_session_id")
    else:
        distribution = []
    return cohort_response(cohorts, distribution)


def cohort_metrics_wafer_level(request: Dict):
    condition, cohorts = cohort_condition_creation(request)
    distribution = distribution_metrics_wafer_level(request)
    if distribution:
        distribution_query = distribution.query.sql_with_params()
        distribution = DistributionMetrics.cohort_metrics(*distribution_query, condition, "wafer_id")
    else:
        distribution = []
    return cohort_response(cohorts, distribution)


def cohort_metrics_use_case_level(request: Dict):
    distribution = None
    if request.get("unit") == "wafer":
        distribution = cohort_metrics_use_case_on_wafer(request)
    elif request.get("unit") == "file":
        distribution = cohort_metrics_use_case_on_file(request)
    else:
        raise ValidationError("this unit is not accepted")
    return distribution


def cohort_metrics_use_case_on_wafer(request: Dict):
    condition, cohorts = cohort_condition_creation(request, unit="wafer")
    input_queryset = get_query_set(request)
    main_distribution = DistributionMetrics.file_distribution(
        input_queryset,
        group_by=["use_case_id", "use_case_name", "ml_model_id", "ml_model_name", "wafer_id", "wafer_threshold"],
    )
    if main_distribution:
        use_case_distribution = DistributionMetrics.use_case_on_wafer(main_distribution, False)
        distribution = DistributionMetrics.cohort_metrics(*use_case_distribution, condition, "use_case_id")
    else:
        distribution = []
    return cohort_response(cohorts, distribution)


def cohort_metrics_use_case_on_file(request: Dict):
    condition, cohorts = cohort_condition_creation(request)
    distribution = distribution_metrics_use_case_on_file(request)
    if distribution:
        use_case_distribution = distribution.query.sql_with_params()
        distribution = DistributionMetrics.cohort_metrics(*use_case_distribution, condition, "use_case_id")
    else:
        distribution = []
    return cohort_response(cohorts, distribution)


def auto_classification_metrics(request):
    result = None
    if request.get("unit") == "wafer":
        result = auto_classification_metrics_wafer_level(request)
    elif request.get("unit") == "file":
        result = auto_classification_metrics_file_level(request)
    else:
        raise ValidationError("this unit is not accepted")
    return result.data


def auto_classification_metrics_timeseries(request):
    result = None
    if request.get("unit") == "wafer":
        result = auto_classification_metrics_wafer_level_timeseries(request)
    elif request.get("unit") == "file":
        result = auto_classification_metrics_file_level_timeseries(request)
    else:
        raise ValidationError("this unit is not accepted")
    return result.data


def accuracy_metrics(request):
    if request.get("unit") == "wafer":
        input_queryset = get_query_set(request)
        distribution = DistributionMetrics.file_distribution(input_queryset, group_by=["wafer_id", "wafer_threshold"])
        return DistributionMetrics.wafer_distribution(distribution)
    elif request.get("unit") == "file":
        input_queryset = get_query_set(request)
        distribution = DistributionMetrics.file_distribution(input_queryset)
        return distribution
    else:
        raise ValidationError("this unit is not accepted")


def accuracy_metrics_timeseries(request):
    result = None
    if request.get("unit") == "wafer":
        result = accuracy_metrics_wafer_level_timeseries(request)
    elif request.get("unit") == "file":
        result = accuracy_metrics_defect_level_timeseries(request)
    else:
        raise ValidationError("this unit is not accepted")
    return result.data


def cohort_response(cohorts, data):
    result = []
    null_case = None
    for cohort in reversed(cohorts):
        exists = False
        for row in data:
            if row.get("cohort") == cohort:
                result.append(row)
                exists = True
                break
            if null_case is None and row.get("cohort") is None:
                null_case = row
        if not exists:
            result.append({"cohort": cohort, "total": 0, "percentage": 0})
    if null_case is not None:
        null_case["cohort"] = "N/A"
        result.append(null_case)
    else:
        result.append({"cohort": "N/A", "total": 0, "percentage": 0})
    return result


def cohort_condition_creation(request, unit=""):
    cohorts = []
    # apologies for the code, I might have lost few hair while writing this. hope this logic is not killed later.
    auto_classification_ranges_list = request.get("file_set_filters").get("file_set__auto_classification")
    if auto_classification_ranges_list is not None:
        del request.get("file_set_filters")["file_set__auto_classification"]
    accuracy_ranges_list = request.get("file_set_filters").get("file_set__accuracy")
    if accuracy_ranges_list is not None:
        del request.get("file_set_filters")["file_set__accuracy"]

    primary_list = []
    primary_variable = None
    secondary_list = []
    secondary_variable = None

    if auto_classification_ranges_list is not None:
        primary_list = auto_classification_ranges_list
        primary_variable = "auto_classified_percentage"
        if accuracy_ranges_list is not None:
            secondary_list = accuracy_ranges_list
            secondary_variable = "accuracy_percentage"
    elif accuracy_ranges_list is not None:
        primary_list = accuracy_ranges_list
        primary_variable = "accuracy_percentage"
    else:
        raise ValidationError("auto_classification or accuracy ranges are not present")

    condition = " case "
    for idx_p, number_p in enumerate(primary_list[: len(primary_list) - 1]):
        primary_start_range = primary_list[idx_p]
        primary_end_range = primary_list[idx_p + 1]
        primary_range_str = str(primary_start_range) + "-" + str(primary_end_range)
        last_p = "<=" if idx_p == len(primary_list) - 2 else "<"
        if secondary_variable is None:
            condition = condition + " when {} >= {} and {} {} {} then '{}' ".format(
                primary_variable, primary_start_range, primary_variable, last_p, primary_end_range, primary_range_str
            )
            cohorts.append(primary_range_str)
        else:
            for idx_s, number in enumerate(secondary_list[: len(secondary_list) - 1]):
                secondary_start_range = secondary_list[idx_s]
                secondary_end_range = secondary_list[idx_s + 1]
                secondary_range_str = (
                    primary_range_str + "," + str(secondary_start_range) + "-" + str(secondary_end_range)
                )
                last_s = "<=" if idx_s == len(secondary_list) - 2 else "<"
                condition = condition + " when {} >= {} and {} {} {} and {} >= {} and {} {} {} then '{}' ".format(
                    primary_variable,
                    primary_start_range,
                    primary_variable,
                    last_p,
                    primary_end_range,
                    secondary_variable,
                    secondary_start_range,
                    secondary_variable,
                    last_s,
                    secondary_end_range,
                    secondary_range_str,
                )
                cohorts.append(secondary_range_str)
    condition = condition + " end "
    return condition, cohorts


def get_query_set(request, additional_filters=[]):
    file_filter = build_query(request.get("file_set_filters"))
    ml_model_filter = build_query(request.get("ml_model_filters"))
    time_function = request.get("time_function")

    more_filters = Q()
    for filter in additional_filters:
        more_filters = more_filters & filter
    return (
        File.objects.filter(file_filter & ml_model_filter & more_filters)
        .annotate(
            file_id=F("id"),
            gt_classification=F("gt_classifications"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            gt_defect_name=F("gt_classifications__gt_classification_annotations__defect__name"),
            model_classification=F("model_classifications"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
            model_defect_name=F("model_classifications__model_classification_annotations__defect__name"),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
            ml_model_id=F("model_classifications__ml_model__id"),
            ml_model_name=F("model_classifications__ml_model__name"),
            use_case_id=F("file_set__use_case_id"),
            use_case_name=F("file_set__use_case__name"),
            wafer_id=F("file_set__wafer"),
            organization_wafer_id=F("file_set__wafer__organization_wafer_id"),
            wafer_status=F("file_set__wafer__status"),
            wafer_threshold=Cast(
                F("file_set__use_case__automation_conditions__threshold_percentage"),
                output_field=FloatField(),
            ),
            upload_session_id=F("file_set__upload_session_id"),
            upload_session_name=F("file_set__upload_session__name"),
            effective_date=Cast(
                time_function("created_ts"),
                DateField(),
            ),
            wafer_created_ts=F("file_set__wafer__created_ts"),
        )
        .values(
            "file_id",
            "gt_defect_id",
            "gt_defect_name",
            "model_defect_id",
            "model_defect_name",
            "confidence",
            "confidence_threshold",
            "ml_model_id",
            "ml_model_name",
            "use_case_id",
            "use_case_name",
            "wafer_id",
            "wafer_status",
            "wafer_threshold",
            "upload_session_id",
            "upload_session_name",
            "effective_date",
            "organization_wafer_id",
            "wafer_created_ts",
        )
        .distinct()
    )
