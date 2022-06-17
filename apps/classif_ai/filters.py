from django.db.models.expressions import F
from apps.classif_ai.service.performance_service import (
    false_negative_file_sets_for_defects,
    false_positive_file_sets_for_defects,
    ground_truth_file_sets_for_defects,
    true_positive_file_sets_for_defects,
)
from django.db.models import Q
from django.db.models.query import QuerySet
from django.forms import DateTimeField
from django_filters import rest_framework as django_filters
from django_filters.fields import RangeField, DateTimeRangeField
from django_filters.filters import DateTimeFromToRangeFilter, CharFilter, NumberFilter
from django_celery_results.models import TaskResult

from rest_framework.exceptions import ValidationError

from apps.classif_ai.models import (
    MlModel,
    FileSet,
    TrainingSessionFileSet,
    TrainingSession,
    UploadSession,
    UseCase,
    Defect,
    UserClassification,
    ModelClassification,
    ModelDetection,
    UserDetection,
    WaferMap,
)
from apps.classif_ai.helpers import get_env, _auto_model_filter


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class MyDateTimeRangeField(RangeField):
    widget = DateTimeRangeField.widget

    def __init__(self, *args, **kwargs):
        input_formats = [
            "%Y-%m-%d %H:%M:%S",  # '2006-10-25 14:30:59'
            "%Y-%m-%d %H:%M:%S.%f",  # '2006-10-25 14:30:59.000200'
            "%Y-%m-%d %H:%M",  # '2006-10-25 14:30'
            "%Y-%m-%d",  # '2006-10-25'
            "%m/%d/%Y %H:%M:%S",  # '10/25/2006 14:30:59'
            "%m/%d/%Y %H:%M:%S.%f",  # '10/25/2006 14:30:59.000200'
            "%m/%d/%Y %H:%M",  # '10/25/2006 14:30'
            "%m/%d/%Y",  # '10/25/2006'
            "%m/%d/%y %H:%M:%S",  # '10/25/06 14:30:59'
            "%m/%d/%y %H:%M:%S.%f",  # '10/25/06 14:30:59.000200'
            "%m/%d/%y %H:%M",  # '10/25/06 14:30'
            "%m/%d/%y",  # '10/25/06'
            "%Y-%m-%d-%H-%M-%S",  # '2006-10-25 14:30:59'
        ]
        fields = (
            DateTimeField(input_formats=input_formats),
            DateTimeField(input_formats=input_formats),
        )
        super(MyDateTimeRangeField, self).__init__(fields, *args, **kwargs)


DateTimeFromToRangeFilter.field_class = MyDateTimeRangeField


class UploadSessionFilterSet(django_filters.FilterSet):
    id__in = NumberInFilter(field_name="id", lookup_expr="in")
    use_case_id__in = NumberInFilter(field_name="use_case_id", lookup_expr="in")
    created_ts = DateTimeFromToRangeFilter(field_name="created_ts", method="filter_by_created_ts")

    def filter_by_created_ts(self, queryset, _, value):
        created_ts__gte = value.start
        created_ts__lte = value.stop
        queryset = queryset.filter(
            Q(created_ts__gte=created_ts__gte, created_ts__lte=created_ts__lte)
            | Q(file_sets__created_ts__gte=created_ts__gte, file_sets__created_ts__lte=created_ts__lte),
        ).distinct()
        return queryset

    class Meta:
        model = UploadSession
        fields = {
            "subscription_id": ["exact"],
            "name": ["exact", "contains"],
            "is_bookmarked": ["exact"],
            "is_live": ["exact"],
        }


class FileSetFilterSet(django_filters.FilterSet):
    id__in = NumberInFilter(field_name="id", lookup_expr="in")
    id__lt = NumberFilter(field_name="id", lookup_expr="lt")
    files__name__contains = CharFilter(field_name="files__name", lookup_expr="icontains")
    created_ts = DateTimeFromToRangeFilter(field_name="created_ts")
    upload_session_id__in = NumberInFilter(field_name="upload_session_id", lookup_expr="in")
    subscription_id__in = NumberInFilter(field_name="subscription_id", lookup_expr="in")
    use_case_id__in = NumberInFilter(field_name="use_case_id", lookup_expr="in")
    is_bookmarked = django_filters.BooleanFilter(field_name="is_bookmarked")
    ml_model_id__in = NumberInFilter(method="get_file_sets_inferenced_by_ml_models")
    ground_truth_label__in = NumberInFilter(method="ground_truth_label_contains")
    ai_predicted_label__in = django_filters.BaseInFilter(method="ai_predicted_label_contains")
    true_positive_label__in = NumberInFilter(method="get_true_positive_file_sets")
    false_positive_label__in = NumberInFilter(method="get_false_positive_file_sets")
    false_negative_label__in = django_filters.BaseInFilter(method="get_false_negative_file_sets")
    # has_ai_predicted_regions__in = django_filters.BaseInFilter(method="has_ai_predicted_regions_in")
    # training_ml_model__in = NumberInFilter(method='get_file_sets_in_training_data_for_ml_models')
    train_type__in = django_filters.BaseInFilter(method="get_file_sets_with_train_type")
    files__referenced_defects__in = NumberInFilter(field_name="files__referenced_defects", lookup_expr="in")
    wafer_id__in = NumberInFilter(field_name="wafer", lookup_expr="in")
    is_confident_defect = django_filters.BooleanFilter(method="confident_defect_filter")
    is_audited = django_filters.BooleanFilter(method="audit_filter")
    wafer_map__status__in = CharFilter(field_name="wafer__status", lookup_expr="exact")
    is_ai_or_gt_classified = django_filters.BooleanFilter(method="ai_or_gt_classified_filter")
    is_accurate = django_filters.BooleanFilter(method="accurate_filter")
    is_auto_model = django_filters.BooleanFilter(method="auto_model_filter")
    is_live = django_filters.BooleanFilter(field_name="upload_session__is_live")
    is_gt_classified = django_filters.BooleanFilter(method="gt_classified")

    def get_true_positive_file_sets(self, queryset: QuerySet, _, value):
        defect_ids = [int(_id) for _id in value]
        ml_model_ids = self.request.query_params.get("ml_model_id__in", None)
        true_positive_file_sets = true_positive_file_sets_for_defects(
            defect_ids, file_set_qs=queryset, ml_model_ids=ml_model_ids
        )
        return true_positive_file_sets

    def get_false_negative_file_sets(self, queryset: QuerySet, _, value):
        defect_ids = [int(_id) for _id in value]
        ml_model_ids = self.request.query_params.get("ml_model_id__in", None)
        false_negative_file_sets = false_negative_file_sets_for_defects(
            defect_ids, file_set_qs=queryset, ml_model_ids=ml_model_ids
        )
        return false_negative_file_sets

    def get_false_positive_file_sets(self, queryset: QuerySet, _, value):
        defect_ids = [int(_id) for _id in value]
        ml_model_ids = self.request.query_params.get("ml_model_id__in", None)
        false_positive_file_sets = false_positive_file_sets_for_defects(
            defect_ids, file_set_qs=queryset, ml_model_ids=ml_model_ids
        )
        return false_positive_file_sets

    def get_file_sets_inferenced_by_ml_models(self, queryset: QuerySet, _, value):
        filters = [
            "ground_truth_label__in",
            "ai_predicted_label__in",
            "true_positive_label__in",
            "false_negative_label__in",
            "false_positive_label__in",
            "is_confident_defect",
            "is_accurate",
            "is_ai_or_gt_classified",
        ]
        exists = False
        for val in filters:
            if val in self.request.query_params:
                exists = True
        if exists:
            return queryset
        ml_model_ids = [int(_id) for _id in value]
        queryset = queryset.filter(
            file_set_inference_queues__ml_model_id__in=ml_model_ids, file_set_inference_queues__status="FINISHED"
        )
        return queryset

    def ground_truth_label_contains(self, queryset: QuerySet, _, value):
        defect_ids = [int(_id) for _id in value]
        gt_file_sets = ground_truth_file_sets_for_defects(defect_ids, file_set_qs=queryset)
        return gt_file_sets

    def ai_predicted_label_contains(self, queryset: QuerySet, _, value):
        include_nvd = False
        if "NVD" in value:
            value.remove("NVD")
            include_nvd = True

        defect_ids = [int(_id) for _id in value]
        ml_model_ids = self.request.query_params.get("ml_model_id__in", None)
        priority = self.request.query_params.get("priority", False)

        if not ml_model_ids:
            ml_model_ids = MlModel.objects.filter(
                status__in=["ready_for_deployment", "deployed_in_prod", "retired"]
            ).values_list("id", flat=True)
        else:
            ml_model_ids = ml_model_ids.split(",")

        model_filter = Q(files__model_classifications__ml_model_id__in=ml_model_ids)
        defect_filter = Q()
        if defect_ids:
            defect_filter = defect_filter | Q(
                files__model_classifications__model_classification_annotations__defect_id__in=defect_ids
            )
        if include_nvd:
            defect_filter = defect_filter | Q(files__model_classifications__is_no_defect=True)

        queryset = queryset.filter(model_filter & defect_filter)

        if priority:
            ordered_defect_ids = get_env().list("ORDERED_DEFECT_IDS", cast=int, default=[1, 2, 4, 5, 3, 6])
            # defect_ids should always have a single element if priority is True
            idx = len(ordered_defect_ids)
            for dd in defect_ids:
                try:
                    t_idx = ordered_defect_ids.index(dd)
                    if t_idx < idx:
                        idx = t_idx
                except ValueError:
                    pass
            queryset = queryset.exclude(
                files__model_classifications__model_classification_annotations__defect_id__in=ordered_defect_ids[0:idx]
            )

        return queryset

    def get_file_sets_with_train_type(self, queryset: QuerySet, _, value):
        train_types = value
        ml_model_ids = self.request.query_params.get("training_ml_model__in", None)
        if ml_model_ids is not None:
            ml_model_ids = ml_model_ids.split(",")
            ml_model_ids = [int(_id) for _id in ml_model_ids]
        return filter_file_sets_with_train_type(queryset, train_types, ml_model_ids)

    def confident_defect_filter(self, queryset: QuerySet, _, value):
        automodel_filter = _auto_model_filter(self)

        auto_classified_filter = Q(
            files__model_classifications__ml_model__confidence_threshold__lte=F(
                "files__model_classifications__model_classification_annotations__confidence"
            )
        )

        if value:
            queryset = queryset.filter(automodel_filter & auto_classified_filter)
        else:
            # could have done threshold>confidence but we also wanted files which dont have classification
            queryset = queryset.filter(automodel_filter & ~auto_classified_filter)

        return queryset

    def audit_filter(self, queryset: QuerySet, _, value):
        # value = True -> return files with threshold <= confidence (ie, autoclassified) & with GT
        # value = False -> return files with threshold > confidence (ie, autoclassified) & without GT
        automodel_filter = _auto_model_filter(self)

        auto_classified_filter = Q(
            files__model_classifications__ml_model__confidence_threshold__lte=F(
                "files__model_classifications__model_classification_annotations__confidence"
            )
        )
        gt_present_filter = Q(files__gt_classifications__isnull=False)
        gt_absent_filter = Q(files__gt_classifications__isnull=True)
        if value:
            queryset = queryset.filter(auto_classified_filter & automodel_filter & gt_present_filter)
        else:
            queryset = queryset.filter(auto_classified_filter & automodel_filter & gt_absent_filter)
        return queryset

    def ai_or_gt_classified_filter(self, queryset: QuerySet, _, value):
        # value = True -> return files with threshold > confidence (ie, autoclassified) | with GT
        # value = False -> return files with threshold > confidence (ie, autoclassified) & without GT
        automodel_filter = _auto_model_filter(self)

        auto_classified_filter = Q(
            files__model_classifications__ml_model__confidence_threshold__lte=F(
                "files__model_classifications__model_classification_annotations__confidence"
            )
        )
        gt_present_filter = Q(files__gt_classifications__isnull=False)
        gt_absent_filter = Q(files__gt_classifications__isnull=True)
        if value:
            queryset = queryset.filter(automodel_filter & (auto_classified_filter | gt_present_filter))
        else:
            queryset = queryset.filter(automodel_filter & ~auto_classified_filter & gt_absent_filter)
        return queryset

    def accurate_filter(self, queryset: QuerySet, _, value):
        automodel_filter = _auto_model_filter(self)

        auto_classified_filter = Q(
            files__model_classifications__ml_model__confidence_threshold__lte=F(
                "files__model_classifications__model_classification_annotations__confidence"
            )
        )
        gt_present_filter = Q(files__gt_classifications__isnull=False)
        accuracy_filter = Q(
            files__gt_classifications__gt_classification_annotations__defect_id=F(
                "files__model_classifications__model_classification_annotations__defect__id"
            )
        )
        if value:
            queryset = queryset.filter(automodel_filter & auto_classified_filter & gt_present_filter & accuracy_filter)
        else:
            queryset = queryset.filter(
                automodel_filter & auto_classified_filter & gt_present_filter & ~accuracy_filter
            )

        return queryset

    # TODO UI shouldn't need to pass model status filter if they are saying auto model or latest undeployed model
    def auto_model_filter(self, queryset: QuerySet, _, value):
        automodel_filter = _auto_model_filter(self)
        return queryset.filter(automodel_filter)

    def gt_classified(self, queryset: QuerySet, _, value):
        gt_present_filter = Q(files__gt_classifications__isnull=False)
        gt_absent_filter = Q(files__gt_classifications__isnull=True)
        if value:
            queryset = queryset.filter(gt_present_filter)
        else:
            queryset = queryset.filter(gt_absent_filter)
        return queryset

    # def get_file_sets_in_training_data_for_ml_models(self, queryset, value, *args, **kwargs):
    # if args:
    # ml_model_ids = value
    # ml_model_ids = [int(_id) for _id in ml_model_ids]
    # queryset = queryset.filter(
    # id__in=TrainingSessionFileSet.objects.filter(
    # training_session__in=TrainingSession.objects.filter(new_ml_model_id__in=ml_model_ids)
    # ).values_list('file_set_id', flat=True)
    # )
    # return queryset

    # TODO: Investigate this filter's behaviour and rewrite it according to the new schema.
    # def has_ai_predicted_regions_in(self, queryset, value, *args, **kwargs):
    # """
    # This function is used to filter the file sets which contain
    # extra_predicted_ai_regions or regions_missed_by_ai or correct_detected_regions_by_ai

    # Didn't separate this function into 3 different filters like
    # (filesets_with_correct_regions, filesets_with_extra_regions and filesets_with_missed_regions)
    # to support OR queries. Like in the approach we used, user can filter all files with incorrect detections
    # (Missed or Extra) in a single API call
    # """
    # if args:
    # types = value
    # ml_model_ids = self.request.query_params.get("ml_model_id__in").split(",")
    # analysis_service = AnalysisService(ml_model_filters={"id__in": ml_model_ids})
    # file_sets = FileSet.objects.none()
    # for type in types:
    # if type == "CORRECT":
    # file_sets = file_sets | FileSet.objects.filter(
    # id__in=File.objects.filter(
    # id__in=analysis_service.detected_file_regions()
    # .values_list("file_id", flat=True)
    # .distinct()
    # ).values_list("file_set_id", flat=True)
    # )
    # elif type == "EXTRA":
    # file_sets = file_sets | FileSet.objects.filter(
    # id__in=File.objects.filter(
    # id__in=FileRegion.objects.filter(
    # ml_model_id__in=ml_model_ids, is_user_feedback=False, is_removed=True
    # )
    # .values_list("file_id", flat=True)
    # .distinct()
    # ).values_list("file_set_id", flat=True)
    # )
    # else:
    # file_sets = file_sets | FileSet.objects.filter(
    # id__in=File.objects.filter(
    # id__in=FileRegion.objects.filter(
    # ml_model_id__in=ml_model_ids, is_user_feedback=True, ai_region_id__isnull=True
    # )
    # .values_list("file_id", flat=True)
    # .distinct()
    # ).values_list("file_set_id", flat=True)
    # )
    # queryset = queryset.filter(id__in=file_sets.values_list("id", flat=True))
    # return queryset

    class Meta:
        # model = FileSet
        fields = ["id__in", "upload_session_id__in", "subscription_id__in", "created_ts", "is_bookmarked"]


class NumberArrayFilter(django_filters.BaseCSVFilter, django_filters.NumberFilter):
    pass


class FileSetLabelFilterSet(django_filters.FilterSet):
    defects__contains = NumberArrayFilter(field_name="defects", lookup_expr="contains")

    class Meta:
        # model = FileSetLabel
        fields = ["file_set_id", "ml_model_id", "defects__contains"]


class UseCaseFilterSet(django_filters.FilterSet):
    # You can use defects or defect_id__in as well. defect_id__in is kept to maintain backward compatibility
    defect_id__in = NumberInFilter(method="get_use_cases_with_associated_defects")

    def get_use_cases_with_associated_defects(self, queryset, _, value):
        queryset = queryset.filter(defects__in=value).distinct()
        return queryset

    class Meta:
        model = UseCase
        fields = {"id": ["in"], "subscription_id": ["exact"], "name": ["exact", "contains"], "defects": ["exact"]}


class MlModelFilterSet(django_filters.FilterSet):
    use_case_id__in = NumberInFilter(field_name="use_case_id", lookup_expr="in")
    # You can use defects or defect_id__in as well. defect_id__in is kept to maintain backward compatibility
    defect_id__in = NumberInFilter(method="get_ml_models_with_associated_defects")
    status = CharFilter(field_name="status")

    def get_ml_models_with_associated_defects(
        self,
        queryset,
        _,
        value,
    ):
        queryset = queryset.filter(defects__in=value).distinct()
        return queryset

    class Meta:
        model = MlModel
        fields = {"id": ["in"], "subscription_id": ["exact"], "name": ["exact", "contains"], "defects": ["exact"]}


class DefectFilterSet(django_filters.FilterSet):
    # You can use use_cases or use_case_id__in as well. use_case_id__in is kept to maintain backward compatibility
    use_case_id__in = NumberInFilter(method="get_defects_with_associated_use_cases")
    # You can use ml_models or ml_model_id__in as well. ml_model_id__in is kept to maintain backward compatibility
    ml_model_id__in = NumberInFilter(method="get_defects_with_associated_ml_models")
    ml_model_id__not_in = NumberInFilter(method="get_defects_with_not_in_ml_models")

    def get_defects_with_associated_use_cases(self, queryset: QuerySet, _, value):
        queryset = queryset.filter(use_cases__in=value).distinct()
        return queryset

    def get_defects_with_associated_ml_models(self, queryset: QuerySet, _, value):
        queryset = queryset.filter(ml_models__in=value).distinct()
        return queryset

    def get_defects_with_not_in_ml_models(self, queryset: QuerySet, _, value):
        queryset = queryset.exclude(ml_models__in=value).distinct()
        return queryset

    class Meta:
        model = Defect
        fields = {
            "id": ["in"],
            "subscription_id": ["exact", "in"],
            "name": ["exact", "contains"],
            "ml_models": ["exact"],
            "use_cases": ["exact"],
        }


def filter_file_sets_with_train_type(queryset, train_types, ml_model_ids=[]):
    """
    This method filters based on training types and optionally, ml model ids.
    Given training_ml_model_id__in param and train_types param, it filters all the file sets
    which were used in training for the given model ids with given train types and gives
    a union of them.

    Eg.
    FS1 and FS2 belongs to train for M1
    FS3 and FS4 belongs to test for M1
    FS2 and FS3 belongs to train for M2
    If user requests for training_ml_model_id__in=M1,M2 and train_types=train response
    will be FS1, FS2 and FS3


    There's a special keyword which can be passed in the train_types param which is NOT_TRAINED.
    This is used filter filesets that don't have any related training sessions. In the
    above scenario, we were returning Union of results but for NOT_TRAINED, we will return
    Intersection of results.

    Eg.
    Total FileSets: FS1, FS2, FS3
    FS1 and FS2 belongs to train for M1
    FS2 and FS3 belongs to train for M2
    If user requests for training_ml_model_id__in=M1,M2 and train_types=NOT_TRAINED,
    the response will have 0 file sets
    """
    not_trained_file_sets = FileSet.objects.none()
    if "NOT_TRAINED" in train_types:
        if ml_model_ids and len(train_types) == 1:
            # filesets null condition makes sure we get some fileset id as it makes an inner join
            # earlier it was creating a left join, so sometimes fileset is null and query becomes ''id not in (null)'', this will skip all records, right way is ''id is not null''
            file_set_ids = TrainingSession.objects.filter(
                Q(new_ml_model_id__in=ml_model_ids) & Q(file_sets__isnull=False)
            ).values_list("file_sets__id", flat=True)
            not_trained_file_sets = queryset.filter(~Q(id__in=file_set_ids)).distinct()
            return not_trained_file_sets
        else:
            not_trained_file_sets = queryset.filter(trainingsession__isnull=True).distinct()
        train_types.remove("NOT_TRAINED")
    if ml_model_ids and train_types:

        queryset = queryset.filter(
            id__in=TrainingSessionFileSet.objects.filter(
                dataset_train_type__in=train_types,
                training_session__in=TrainingSession.objects.filter(new_ml_model_id__in=ml_model_ids),
            ).values_list("file_set_id", flat=True)
        ).distinct()
    else:
        queryset = queryset.filter(
            id__in=TrainingSessionFileSet.objects.filter(
                dataset_train_type__in=train_types,
            ).values_list("file_set_id", flat=True)
        ).distinct()
    return queryset | not_trained_file_sets


class UserClassificationFilterSet(django_filters.FilterSet):
    def __init__(self, data, *args, **kwargs):
        if not data.get("user") and kwargs.get("request", None) is not None:
            data = data.copy()
            data["user"] = kwargs["request"].user.id
        if kwargs.get("request") is not None and kwargs["request"].method == "GET" and not data.get("file"):
            raise ValidationError("File is mandatory")
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = UserClassification
        fields = {"id": ["exact"], "file": ["exact"], "user": ["exact"]}


class UserDetectionFilterSet(django_filters.FilterSet):
    def __init__(self, data, *args, **kwargs):
        if not data.get("user") and kwargs.get("request", None) is not None:
            data = data.copy()
            data["user"] = kwargs["request"].user.id
        if kwargs.get("request") is not None and kwargs["request"].method == "GET" and not data.get("file"):
            raise ValidationError("File is mandatory")
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = UserDetection
        fields = {"id": ["exact"], "file": ["exact"], "user": ["exact"]}


class MLModelClassificationFilterSet(django_filters.FilterSet):
    def __init__(self, data, *args, **kwargs):
        if (
            kwargs.get("request") is not None
            and kwargs["request"].method == "GET"
            and not (data.get("file_id") or data.get("file"))
            and not data.get("file__file_set")
        ):
            raise ValidationError("File is mandatory")
        if (
            kwargs.get("request") is not None
            and kwargs["request"].method == "GET"
            and not (data.get("ml_model_id") or data.get("ml_model"))
        ):
            raise ValidationError("MLModel is mandatory")
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = ModelClassification
        fields = {
            "id": ["exact"],
            "file_id": ["exact"],
            "file": ["exact"],
            "ml_model_id": ["exact"],
            "ml_model": ["exact"],
            "file__file_set": ["exact"],
        }


# TODO Need to implement common FilterFactory
class MLModelDetectionFilterSet(django_filters.FilterSet):
    def __init__(self, data, *args, **kwargs):
        if (
            kwargs.get("request") is not None
            and kwargs["request"].method == "GET"
            and not (data.get("file_id") or data.get("file"))
            and not data.get("file__file_set")
        ):
            raise ValidationError("File is mandatory")
        if (
            kwargs.get("request") is not None
            and kwargs["request"].method == "GET"
            and not (data.get("ml_model_id") or data.get("ml_model"))
        ):
            raise ValidationError("MLModel is mandatory")
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = ModelDetection
        fields = {
            "id": ["exact"],
            "file_id": ["exact"],
            "file": ["exact"],
            "ml_model_id": ["exact"],
            "ml_model": ["exact"],
            "file__file_set": ["exact"],
        }


class WaferMapFilterSet(django_filters.FilterSet):
    upload_session_id__in = NumberInFilter(field_name="file_sets__upload_session_id", lookup_expr="in", distinct=True)
    created_ts = DateTimeFromToRangeFilter(field_name="created_ts")
    id__gt = NumberFilter(field_name="id", lookup_expr="gt")
    id__lt = NumberFilter(field_name="id", lookup_expr="lt")

    class Meta:
        model = WaferMap
        fields = {
            "id": ["exact", "in"],
            "organization_wafer_id": ["exact", "in"],
            "tags__id": ["exact", "in"],
            "status": ["exact", "in"],
        }


class TaskResultFilterSet(django_filters.FilterSet):
    class Meta:
        model = TaskResult
        fields = {"task_id": ["exact", "in"], "task_name": ["exact", "in"], "status": ["exact", "in"]}
