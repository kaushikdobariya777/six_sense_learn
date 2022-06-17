from typing import List
from django.db.models.query import QuerySet

from apps.classif_ai.models import (
    FileSet,
)
from django.db.models import Q, F


def true_positive_file_sets_for_defects(
    defect_ids: List[int], use_case_id: int = None, ml_model_ids: List[int] = None, file_set_qs: QuerySet = None
) -> QuerySet:
    use_case_filter = Q()
    ml_model_filter = Q()
    if use_case_id:
        use_case_filter = Q(files__model_classifications__ml_model__use_case_id=use_case_id)
    if ml_model_ids:
        ml_model_filter = Q(files__model_classifications__ml_model_id__in=ml_model_ids)
    file_sets = FileSet.objects.none()
    if file_set_qs:
        file_sets = file_set_qs
    file_sets = file_sets.filter(
        Q(
            files__model_classifications__model_classification_annotations__defect__id=F(
                "files__gt_classifications__gt_classification_annotations__defect_id"
            )
        )
        & Q(files__gt_classifications__gt_classification_annotations__defect_id__in=defect_ids)
        & use_case_filter
        & ml_model_filter
    )
    return file_sets


def false_positive_file_sets_for_defects(
    defect_ids: List[int], use_case_id: int = None, ml_model_ids: List[int] = None, file_set_qs: QuerySet = None
) -> QuerySet:
    use_case_filter = Q()
    ml_model_filter = Q()
    if use_case_id:
        use_case_filter = Q(files__model_classifications__ml_model__use_case_id=use_case_id)
    if ml_model_ids:
        ml_model_filter = Q(files__model_classifications__ml_model_id__in=ml_model_ids)
    file_sets = FileSet.objects.none()
    if file_set_qs:
        file_sets = file_set_qs
    file_sets = file_sets.filter(
        ~Q(
            files__model_classifications__model_classification_annotations__defect__id=F(
                "files__gt_classifications__gt_classification_annotations__defect_id"
            )
        )
        & Q(files__model_classifications__model_classification_annotations__defect_id__in=defect_ids)
        & use_case_filter
        & ml_model_filter
    )
    return file_sets


def false_negative_file_sets_for_defects(
    defect_ids: List[int], use_case_id: int = None, ml_model_ids: List[int] = None, file_set_qs: QuerySet = None
) -> QuerySet:
    use_case_filter = Q()
    ml_model_filter = Q()
    if use_case_id:
        use_case_filter = Q(files__model_classifications__ml_model__use_case_id=use_case_id)
    if ml_model_ids:
        ml_model_filter = Q(files__model_classifications__ml_model_id__in=ml_model_ids)
    file_sets = FileSet.objects.none()
    if file_set_qs:
        file_sets = file_set_qs
    file_sets = file_sets.filter(
        ~Q(
            files__model_classifications__model_classification_annotations__defect__id=F(
                "files__gt_classifications__gt_classification_annotations__defect_id"
            )
        )
        & Q(files__gt_classifications__gt_classification_annotations__defect_id__in=defect_ids)
        & use_case_filter
        & ml_model_filter
    )
    return file_sets


def ground_truth_file_sets_for_defects(
    defect_ids: List[int], use_case_id: int = None, file_set_qs: QuerySet = None
) -> QuerySet:
    use_case_filter = Q()
    if use_case_id:
        use_case_filter = Q(files__model_classifications__ml_model__use_case_id=use_case_id)
    file_sets = FileSet.objects.none()
    if file_set_qs is not None:
        file_sets = file_set_qs
    file_sets = file_sets.filter(
        Q(files__gt_classifications__gt_classification_annotations__defect_id__in=defect_ids) & use_case_filter
    )
    return file_sets
