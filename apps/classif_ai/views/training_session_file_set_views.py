import logging
from datetime import datetime, MINYEAR

import pytz
from django.db import connection, transaction
from django.db.models import Q, Prefetch
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django_filters import rest_framework as django_filters

from apps.classif_ai.helpers import prepare_detection_defects, prepare_classification_defects
from apps.classif_ai.models import TrainingSessionFileSet, FileSet, FileRegion, TrainingSession
from apps.classif_ai.serializers import TrainingSessionFileSetSerializer, FileRegionSerializer
from apps.classif_ai.services import AnalysisService
from apps.classif_ai.tasks import perform_retraining
from common.views import BaseViewSet
from apps.classif_ai.filters import FileSetFilterSet

logger = logging.getLogger(__name__)


class TrainingSessionFileSetViewSet(BaseViewSet):
    queryset = TrainingSessionFileSet.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [django_filters.DjangoFilterBackend]

    def list(self, request, *args, **kwargs):
        file_set_filters = {}
        for key, val in request.query_params.items():
            if key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            else:
                file_set_filters[key] = val.split(",")
        analysis_service = AnalysisService(file_set_filters)
        file_sets = analysis_service.file_sets()
        queryset = TrainingSessionFileSet.objects.filter(file_set__in=file_sets)
        serializer = TrainingSessionFileSetSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        training_session_id = request.data.get("training_session", None)
        file_set_ids = request.data.get("file_set_ids", None)

        file_set_filters = {}
        ml_model_filters = {}
        dont_include_defects = []
        for key, val in request.data.items():
            if key == "subscription_id":
                file_set_filters["subscription_id__in"] = [val]
            elif key == "training_session":
                continue
            elif key == "use_case_id":
                ml_model_filters["use_case_id"] = val
            elif key == "dont_include_defects":
                dont_include_defects = val
            else:
                file_set_filters[key] = [item for item in val]

        if file_set_ids:
            file_set_filters = {"id__in": file_set_ids}

        analysis_service = AnalysisService(file_set_filters, ml_model_filters)

        ml_models = analysis_service.ml_models()
        file_sets = FileSet.objects.filter(
            files__in=analysis_service.files().filter(
                Q(file_regions__detection_correctness__isnull=False)
                | Q(file_regions__classification_correctness__isnull=False)
                | Q(file_regions__is_user_feedback=True, file_regions__ai_region__isnull=True),
                file_regions__ml_model__in=ml_models,
            )
        ).prefetch_related(
            Prefetch(
                "files__file_regions",
                queryset=FileRegion.objects.filter(
                    Q(detection_correctness__isnull=False)
                    | Q(classification_correctness__isnull=False)
                    | Q(is_user_feedback=True)
                ).order_by("-updated_ts"),
            )
        )

        training_file_sets = []
        all_defect_ids = set()
        for file_set in file_sets:
            defects = {}
            # Find which model to use to pick up the latest feedback
            ml_model_id_for_gt = None
            latest_updated_ts = datetime(MINYEAR, 1, 1, 0, 0, 0, 0, pytz.UTC)
            for file in file_set.files.all():
                if file.file_regions.first():
                    if file.file_regions.first().updated_ts > latest_updated_ts:
                        ml_model_id_for_gt = file.file_regions.first().ml_model_id
                        latest_updated_ts = file.file_regions.first().updated_ts
            for file in file_set.files.all():
                # Collect all valid GT file regions for ml_model_id_for_gt
                if defects.get(file.id, None) is None:
                    defects[file.id] = []
                for region in file.file_regions.all():
                    if region.ml_model_id == ml_model_id_for_gt and region in analysis_service.gt_regions():
                        defect_data = FileRegionSerializer(instance=region).data
                        for defect_id in list(defect_data["defects"]):
                            if int(defect_id) in dont_include_defects:
                                del defect_data["defects"][defect_id]
                        if not defect_data["defects"]:
                            continue
                        defects[file.id].append(defect_data)
                        all_defect_ids.update(list(defect_data["defects"]))
            training_file_sets.append(
                TrainingSessionFileSet(file_set=file_set, training_session_id=training_session_id, defects=defects)
            )
        training_session = TrainingSession.objects.get(id=training_session_id)
        old_training_session_file_sets = TrainingSessionFileSet.objects.filter(
            training_session__new_ml_model_id=training_session.old_ml_model_id
        )
        for otfs in old_training_session_file_sets:
            skip_this_file_set = False
            for ntfs in training_file_sets:
                if ntfs.file_set_id == otfs.file_set_id:
                    skip_this_file_set = True
                    break
            if skip_this_file_set is False:
                for file_id, file_regions in otfs.defects.items():
                    remove_indexes = []
                    for idx, file_region in enumerate(file_regions):
                        for defect_id in list(file_region["defects"]):
                            if int(defect_id) in dont_include_defects:
                                del file_region["defects"][defect_id]
                        if not file_region["defects"]:
                            remove_indexes.append(idx)
                    for index in sorted(remove_indexes, reverse=True):
                        del file_regions[index]

                training_file_sets.append(
                    TrainingSessionFileSet(
                        file_set_id=otfs.file_set_id,
                        training_session_id=training_session_id,
                        defects=otfs.defects,
                        dataset_train_type=otfs.dataset_train_type,
                        belongs_to_old_model_training_data=True,
                    )
                )
                for file_id, file_regions in otfs.defects.items():
                    for file_region in file_regions:
                        all_defect_ids.update(list(file_region["defects"]))
        for i in range(0, len(training_file_sets), 50):
            TrainingSessionFileSet.objects.bulk_create(training_file_sets[i : i + 50])
        new_ml_model = training_session.new_ml_model
        new_ml_model.defects.set(list(all_defect_ids))
        perform_retraining.delay(training_session_id, schema=connection.schema_name)
        return Response(f"FileSets added to TrainingSession {training_session_id}", status=status.HTTP_200_OK)

    def validate_training_session(self, query_params) -> TrainingSession:
        train_ml_model_id = query_params.get("train_ml_model_id", None)
        use_case_id = query_params.get("use_case_id", None)
        if not train_ml_model_id and not use_case_id:
            raise ValidationError("train_ml_model_id and use_case_id are required query parameter.")
        try:
            training_session = TrainingSession.objects.get(
                new_ml_model_id=train_ml_model_id, new_ml_model__use_case_id=use_case_id
            )
            return training_session
        except TrainingSession.DoesNotExist:
            raise ValidationError(f"Training session does not exist for {train_ml_model_id} ml_model_id")

    @action(detail=False, methods=["post"], url_name="bulk-create", url_path="bulk-create")
    def bulk_create(self, request):
        """
        Add bulk files to training
        """
        with transaction.atomic():
            query_params = request.query_params
            training_session = self.validate_training_session(query_params)
            training_session_new_ml_model_status = training_session.new_ml_model.status
            if training_session_new_ml_model_status != "draft":
                return Response(
                    "training session's model status is {}, status should be draft".format(
                        training_session_new_ml_model_status
                    ),
                    status=status.HTTP_406_NOT_ACCEPTABLE,
                )
            file_set_filter = FileSetFilterSet(query_params, queryset=FileSet.objects.all(), request=request)
            file_sets = file_set_filter.qs.filter(
                Q(files__gt_classifications__isnull=False) | Q(files__gt_detections__isnull=False)
            )
            training_session.copy_files_from_fileset_qs(file_sets, training_session.created_by.id)

        # this call could be sent to queue and made async
        training_session.copy_gt_defects(file_sets)
        return Response(status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["delete"], url_name="bulk-delete", url_path="bulk-delete")
    def bulk_delete(self, request):
        """
        Delete bulk files from training
        """
        with transaction.atomic():
            query_params = request.query_params
            training_session = self.validate_training_session(query_params)
            file_set_filter = FileSetFilterSet(query_params, queryset=FileSet.objects.all(), request=request)
            file_sets = file_set_filter.qs
            TrainingSessionFileSet.objects.filter(training_session=training_session, file_set__in=file_sets).delete()

        return Response(status=status.HTTP_200_OK)
