import csv
from functools import reduce
from operator import ior
import logging
import sys
import tempfile
from calendar import monthrange
from datetime import datetime, timedelta
from pydoc import locate
import requests

import pytz
from django.contrib.postgres.aggregates import JSONBAgg, ArrayAgg
from django.db.models import Case, When, Value, IntegerField, Q
from django.db.models.aggregates import Count
from django.db.models.functions import TruncWeek, TruncMonth, TruncDay
from django.http import HttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.classif_ai.helpers import convert_datetime_to_str, get_env
from apps.classif_ai.models import (
    FileRegion,
    JsonKeys,
    Defect,
    MlModel,
    File,
    FileSet,
    UploadSession,
    FileSetInferenceQueue,
)
from apps.classif_ai.services import AnalysisService
from apps.subscriptions.models import Subscription
from sixsense import settings

logger = logging.getLogger(__name__)


class PerformanceSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        file_set_filters = {}
        ml_model_filters = {}
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte
        records_with_feedback = False
        auto_model = False

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "records_with_feedback":
                if val == "true" or val is True:
                    records_with_feedback = True
                else:
                    records_with_feedback = False
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "train_type__in":
                file_set_filters["trainingsessionfileset__dataset_train_type__in"] = val.split(",")
            elif key == "auto_model_selection":
                auto_model = True
            else:
                file_set_filters[key] = val.split(",")
        analysis_service = AnalysisService(file_set_filters, ml_model_filters, auto_model)
        if file_set_filters.get(
            "trainingsessionfileset__dataset_train_type__in", None
        ) is not None and ml_model_filters.get("id__in"):
            file_set_filters[
                "trainingsessionfileset__training_session__new_ml_model_id__in"
            ] = analysis_service.ml_models().values_list("id", flat=True)

        # Following queries are commented because they take too long.
        # all_defect_ids = list(analysis_service.file_regions().annotate(
        # defect_ids=JsonKeys('defects')).values_list('defect_ids', flat=True).distinct())
        # defects = Defect.objects.filter(id__in=all_defect_ids).values('id', 'name')
        # defects_count = len(defects)

        if records_with_feedback:
            if analysis_service.ml_models().count() == 1:
                response_data = {
                    "data_summary": {
                        "images_count": analysis_service.file_sets_with_feedback().count(),
                    },
                    "performance_summary": {
                        "overall_metrics": analysis_service.overall_metrics(),
                        "detection_metrics": analysis_service.detection_metrics(),
                        "classification_metrics": analysis_service.classification_metrics(),
                    },
                }
            else:
                response_data = {
                    "data_summary": {
                        "images_count": analysis_service.file_sets_with_feedback().count(),
                    },
                    "performance_summary": {
                        "overall_metrics": "N/A",
                        "detection_metrics": "N/A",
                        "classification_metrics": "N/A",
                    },
                }
        else:
            response_data = {
                "data_summary": {
                    "images_count": analysis_service.file_sets().count(),
                },
                "performance_summary": {
                    "overall_metrics": "N/A",
                    "detection_metrics": "N/A",
                    "classification_metrics": "N/A",
                },
            }
        return Response(response_data, status=status.HTTP_200_OK)

    @action(
        methods=[
            "GET",
        ],
        detail=False,
    )
    def accuracy_trend(self, request):

        file_set_filters = {}
        ml_model_filters = {}
        time_format = "daily"
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "time_format":
                time_format = val
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "train_type__in":
                file_set_filters["trainingsessionfileset__dataset_train_type__in"] = val.split(",")
            else:
                file_set_filters[key] = val.split(",")
        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        if file_set_filters.get(
            "trainingsessionfileset__dataset_train_type__in", None
        ) is not None and ml_model_filters.get("id__in"):
            file_set_filters[
                "trainingsessionfileset__training_session__new_ml_model_id__in"
            ] = analysis_service.ml_models().values_list("id", flat=True)

        if time_format == "monthly":
            file_set_time_vals = (
                analysis_service.file_sets().values("created_ts__month", "created_ts__year").distinct()
            )
        elif time_format == "weekly":
            file_set_time_vals = analysis_service.file_sets().values("created_ts__week", "created_ts__year").distinct()
        else:
            file_set_time_vals = analysis_service.file_sets().values("created_ts__date", "created_ts__year").distinct()

        graphs = {"classification_accuracy": {}, "detection_accuracy": {}, "overall_accuracy": {}}
        for time_dict in file_set_time_vals:
            # expr = {"created_ts__date": time}
            if time_format == "monthly":
                month = time_dict["created_ts__month"]
                year = time_dict["created_ts__year"]
                file_set_filters["created_ts__month"] = month
                file_set_filters["created_ts__year"] = year
                last_date = monthrange(year, month)[1]
                time_str = f"{year}-{month}-1 : {year}-{month}-{last_date}"
                # expr = {"created_ts__month": time}
            elif time_format == "weekly":
                week = time_dict["created_ts__week"]
                year = time_dict["created_ts__year"]
                file_set_filters["created_ts__week"] = week
                file_set_filters["created_ts__year"] = year
                monday = datetime.strptime(f"{year}-{week-1}-1", "%Y-%W-%w").date()
                time_str = f"{monday.strftime('%Y-%m-%d')} : {(monday + timedelta(days=6.9)).strftime('%Y-%m-%d')}"
                # expr = {"created_ts__week": time}
            else:
                file_set_filters["created_ts__date"] = time_dict["created_ts__date"]
                time_str = time_dict["created_ts__date"].strftime("%Y-%m-%d")
            analysis_service = AnalysisService(file_set_filters=file_set_filters, ml_model_filters=ml_model_filters)
            graphs["classification_accuracy"][time_str] = analysis_service.classification_accuracy()
            graphs["detection_accuracy"][time_str] = analysis_service.detection_accuracy()
            graphs["overall_accuracy"][time_str] = analysis_service.overall_accuracy()

        # time_val = None
        #
        #
        # for file_set in file_set_time_vals:
        # if file_set['time_val'] != time_val and time_val:
        # analysis_service = AnalysisService(file_set_filters={"created_ts": time_val.strftime("%Y-%m-%d")})
        # graphs['classification_accuracy'][time_val] = analysis_service.classification_accuracy()
        # graphs['detection_accuracy'][time_val] = analysis_service.detection_accuracy()
        # time_val = file_set['time_val']
        # if file_set['time_val'] == time_val or not time_val:
        # time_val = file_set['time_val']
        return Response(graphs)

    @action(methods=["GET"], detail=False)
    def confusion_matrix(self, request):
        file_set_filters = {}
        ml_model_filters = {}
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "train_type__in":
                file_set_filters["trainingsessionfileset__dataset_train_type__in"] = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            else:
                file_set_filters[key] = val.split(",")

        if list(
            MlModel.objects.filter(id__in=ml_model_filters["id__in"]).values_list(
                "use_case__classification_type", flat=True
            )
        ) != ["SINGLE_LABEL"]:
            return Response(
                "All ML Models should be of single label classification type", status=status.HTTP_400_BAD_REQUEST
            )

        defect_mapping = {}
        for defect in Defect.objects.all():
            defect_mapping[defect.id] = {
                "id": defect.id,
                "code": defect.organization_defect_code,
                "name": defect.name,
                "organization_defect_code": defect.organization_defect_code,
            }

        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        value_args = ["id", "file_id", "file__file_set_id", "is_user_feedback", "defects"]
        pred_regions = list(analysis_service.ai_regions_with_feedback().order_by("file_id").values(*value_args))
        true_regions = list(analysis_service.gt_regions().order_by("file_id").values(*value_args))
        resp = analysis_service.confusion_matrix(true_regions, pred_regions, defect_mapping)

        return Response(resp)


class DetailedReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        ml_model_ids = request.query_params.get("ml_model_id__in", None)
        ml_model_ids = ml_model_ids.split(",")
        if len(MlModel.objects.filter(id__in=ml_model_ids).values_list("code", flat=True).distinct()) != 1:
            return Response(
                {"message": "All selected ML models should have the same code"}, status=status.HTTP_400_BAD_REQUEST
            )

        file_set_filters = {}
        ml_model_filters = {}
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "train_type__in":
                file_set_filters["trainingsessionfileset__dataset_train_type__in"] = val.split(",")
            else:
                file_set_filters[key] = val.split(",")
        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        if file_set_filters.get(
            "trainingsessionfileset__dataset_train_type__in", None
        ) is not None and ml_model_filters.get("id__in"):
            file_set_filters[
                "trainingsessionfileset__training_session__new_ml_model_id__in"
            ] = analysis_service.ml_models().values_list("id", flat=True)
        venn_data = {
            "ai_count": analysis_service.total_ai_region_count(),
            "gt_count": analysis_service.ground_truth_count(),
            "correct_count": analysis_service.correct_detection_count(),
        }
        response = {"venn_data": venn_data}
        return Response(response, status=status.HTTP_200_OK)


class ClassWiseMatrix(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        ml_model_ids = request.query_params.get("ml_model_id__in", None)
        ml_model_ids = ml_model_ids.split(",")
        if len(MlModel.objects.filter(id__in=ml_model_ids).values_list("code", flat=True).distinct()) != 1:
            return Response(
                {"message": "All selected ML models should have the same code"}, status=status.HTTP_400_BAD_REQUEST
            )

        file_set_filters = {}
        ml_model_filters = {}
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "train_type__in":
                file_set_filters["trainingsessionfileset__dataset_train_type__in"] = val.split(",")
            else:
                file_set_filters[key] = val.split(",")
        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        if file_set_filters.get(
            "trainingsessionfileset__dataset_train_type__in", None
        ) is not None and ml_model_filters.get("id__in"):
            file_set_filters[
                "trainingsessionfileset__training_session__new_ml_model_id__in"
            ] = analysis_service.ml_models().values_list("id", flat=True)

        result = analysis_service.class_wise_matrix_data()
        response = {"class_wise_matrix_data": result}
        return Response(response, status=status.HTTP_200_OK)


class ApplicationChartsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        filtered_defects = []
        time_format = "daily"

        file_set_filters = {}
        ml_model_filters = {}
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now(tz=pytz.UTC)
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte
        priority = False
        unimp_defects = []
        auto_model = False

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "defect_id__in":
                filtered_defects = val.split(",")
                file_set_filters["files__file_regions__defects__has_any_keys"] = filtered_defects
            elif key == "time_format":
                time_format = val
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "priority":
                priority = True
            elif key == "insignificant_defect_ids":
                unimp_defects = val.split(",")
            elif key == "auto_model_selection":
                auto_model = True
            else:
                file_set_filters[key] = val.split(",")

        analysis_service = AnalysisService(file_set_filters, ml_model_filters, auto_model)
        imp_defects = list(Defect.objects.filter(~Q(id__in=unimp_defects)).values_list("id", flat=True))

        scatter_yield_loss = analysis_service.calculate_yield_loss_scatter_plot(imp_defects, time_format)
        yield_loss = analysis_service.calculate_yield_loss(imp_defects)

        defects_id_name_map = {}
        defect_v_count = []
        ai_file_sets = list(
            analysis_service.file_sets()
            .filter(files__file_regions__in=analysis_service.ai_regions())
            .annotate(defects=JsonKeys("files__file_regions__defects"))
            .order_by("id")
            .values("id", "meta_info__MachineNo", "defects")
            .distinct()
        )

        if filtered_defects:
            defects = Defect.objects.filter(id__in=filtered_defects)
        else:
            defects = Defect.objects.all()

        for defect in defects:
            defects_id_name_map[defect.id] = defect.name

        defect_yield_loss = analysis_service.yield_loss_trend_grouped_by_defect(
            defect_id_map=defects_id_name_map, imp_defects=imp_defects, time_format=time_format, priority=priority
        )

        file_set_id_defect_ids = {}
        ordered_defect_ids = get_env().list("ORDERED_DEFECT_IDS", cast=int, default=[1, 2, 4, 5, 3, 6])
        ordered_defect_ids = ordered_defect_ids + list(
            Defect.objects.exclude(id__in=ordered_defect_ids).order_by("created_ts").values_list("id", flat=True)
        )

        if priority:
            new_ai_file_sets = []
            current_priority_record = {}
            for ai_file_set in ai_file_sets:
                if not current_priority_record:
                    current_priority_record = ai_file_set
                elif current_priority_record["id"] != ai_file_set["id"]:
                    new_ai_file_sets.append(current_priority_record)
                    current_priority_record = ai_file_set
                else:
                    current_priority_record_defect_priority = ordered_defect_ids.index(
                        int(current_priority_record["defects"])
                    )
                    ai_file_set_defect_priority = ordered_defect_ids.index(int(ai_file_set["defects"]))
                    if ai_file_set_defect_priority < current_priority_record_defect_priority:
                        current_priority_record = ai_file_set
            if current_priority_record:
                new_ai_file_sets.append(current_priority_record)
            ai_file_sets = new_ai_file_sets

        file_set_defect_cache = {}
        for file_set in ai_file_sets:
            file_set_id = file_set["id"]
            defect_id = int(file_set["defects"])  # loop through all defect ids in that file_region
            if defect_id in filtered_defects or not filtered_defects:  # check defect was present in filters
                if file_set_defect_cache.get(file_set_id, None):
                    if defect_id in file_set_defect_cache[file_set_id]:
                        continue
                    else:
                        file_set_defect_cache[file_set_id].append(defect_id)
                else:
                    file_set_defect_cache[file_set_id] = [defect_id]

                try:
                    defect_name = defects_id_name_map[defect_id]  # get defect name
                except KeyError:
                    continue
                try:
                    machine = file_set["meta_info__MachineNo"]
                except:
                    machine = None

                defect_v_count = analysis_service.defect_v_count(defect_id, defect_name, machine, defect_v_count)

        if not filtered_defects:
            file_sets_with_nvd = analysis_service.file_sets().filter(
                files__file_regions__isnull=True, file_set_inference_queues__status="FINISHED"
            )
            for file_set_with_nvd in file_sets_with_nvd.values("meta_info__MachineNo", "created_ts"):
                try:
                    machine = file_set_with_nvd["meta_info__MachineNo"]
                except:
                    machine = None
                defect_v_count = analysis_service.defect_v_count("NVD", "Non Visible Defect", machine, defect_v_count)

        response = {
            "defect_v_count": defect_v_count,
            "yield_loss_scatter_plot": scatter_yield_loss,
            "yield_loss": yield_loss,
            "yield_loss_trend_grouped_by_defect": defect_yield_loss,
        }

        return Response(response, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["GET"],
    )
    def overkill_trend(self, request):

        file_set_filters = {}
        ml_model_filters = {}
        time_format = "daily"
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte
        auto_model = False
        include_defects = []

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "time_format":
                time_format = val
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "insignificant_defect_ids":
                include_defects = val.split(",")
            elif key == "auto_model_selection":
                auto_model = True
            else:
                file_set_filters[key] = val.split(",")

        exclude_defects = list(Defect.objects.filter(~Q(id__in=include_defects)).values_list("id", flat=True))
        analysis_service = AnalysisService(file_set_filters, ml_model_filters, auto_model)
        if not auto_model:
            file_sets = (
                analysis_service.file_sets()
                .filter(
                    Q(
                        files__file_regions__defects__has_any_keys=include_defects,
                        files__file_regions__is_user_feedback=False,
                    )
                    | Q(files__file_regions__isnull=True)
                )
                .values("id", "meta_info__lot_id")
                .distinct()
            )
        else:
            filters = []
            model_id_file_set_map = analysis_service.get_auto_model_file_set_ids_map()
            for model_id, file_set_ids in model_id_file_set_map.items():
                file_set_ids = list(file_set_ids)
                # filter =  (Q(
                # Q(
                # files__file_regions__defects__has_any_keys=include_defects,
                # files__file_regions__is_user_feedback=False,
                # files__file_regions__ml_model_id=model_id
                # ) |
                # ~ Q(
                # id__in=FileRegion.objects.filter(
                # ml_model_id=model_id, is_user_feedback=False,
                # ).values_list('file__file_set__id', flat=True)
                # )
                # ) & Q(
                # id__in=file_set_ids
                # )
                # )
                filter = ~Q(
                    id__in=FileRegion.objects.filter(
                        ml_model_id=model_id, is_user_feedback=False, defects__has_any_keys=exclude_defects
                    ).values_list("file__file_set__id", flat=True)
                ) & Q(id__in=file_set_ids)
                filters.append(filter)
            or_filters = reduce(ior, filters)
            file_sets = FileSet.objects.filter(or_filters).values("id", "meta_info__lot_id").distinct()

        if time_format == "monthly":
            distinct_meta_info = (
                analysis_service.file_sets()
                .filter(file_set_inference_queues__status="FINISHED")
                .values("meta_info__lot_id", "meta_info__InitialTotal", "meta_info__MachineNo")
                .distinct()
                .annotate(time_val=TruncMonth("created_ts"))
            )
            file_sets = file_sets.annotate(time_val=TruncMonth("created_ts"))
        elif time_format == "weekly":
            distinct_meta_info = (
                analysis_service.file_sets()
                .filter(file_set_inference_queues__status="FINISHED")
                .values("meta_info__lot_id", "meta_info__InitialTotal", "meta_info__MachineNo")
                .distinct()
                .annotate(time_val=TruncWeek("created_ts"))
            )

            file_sets = file_sets.annotate(time_val=TruncWeek("created_ts"))
            # file_sets = analysis_service.file_sets().exclude(
            # files__file_regions__defects__has_any_keys=exclude_defects
            # ).values('id', 'meta_info__lot_id').distinct().annotate(time_val=TruncWeek('created_ts'))
        else:
            distinct_meta_info = (
                analysis_service.file_sets()
                .filter(file_set_inference_queues__status="FINISHED")
                .values("meta_info__lot_id", "meta_info__InitialTotal", "meta_info__MachineNo")
                .distinct()
                .annotate(time_val=TruncDay("created_ts"))
            )

            # file_sets = analysis_service.file_regions().exclude(
            # defects__has_any_keys=exclude_defects
            # ).values('file__file_set_id', 'file__file_set__meta_info__lot_id').distinct().annotate(
            # time_val=TruncDay('file__file_set__created_ts')
            # )
            file_sets = file_sets.annotate(time_val=TruncMonth("created_ts"))

        overkill_scatter_plot = {}
        overkill_trend = {}
        meta_info_grouped_by_time_val = {}
        file_set_id_grouped_by_time_val = {}
        checked_in_lot_ids = {}
        for meta_info in distinct_meta_info:
            time_val = meta_info["time_val"]
            lot_id = meta_info["meta_info__lot_id"]
            if not time_val in checked_in_lot_ids:
                checked_in_lot_ids[time_val] = []
            if meta_info_grouped_by_time_val.get(time_val, None) is None:
                if lot_id not in checked_in_lot_ids[time_val]:
                    meta_info_grouped_by_time_val[time_val] = [
                        [lot_id, meta_info["meta_info__InitialTotal"], meta_info["meta_info__MachineNo"]]
                    ]
                    checked_in_lot_ids[time_val].append(lot_id)
            else:
                if lot_id not in checked_in_lot_ids[time_val]:
                    meta_info_grouped_by_time_val[time_val].append(
                        [lot_id, meta_info["meta_info__InitialTotal"], meta_info["meta_info__MachineNo"]]
                    )
                    checked_in_lot_ids[time_val].append(lot_id)

        for file_set in file_sets:
            time_val = file_set["time_val"]
            lot_id = file_set["meta_info__lot_id"]
            if file_set_id_grouped_by_time_val.get(time_val, None) is None:
                file_set_id_grouped_by_time_val[time_val] = {lot_id: [file_set["id"]]}
            else:
                if file_set_id_grouped_by_time_val[time_val].get(lot_id, None) is None:
                    file_set_id_grouped_by_time_val[time_val][lot_id] = [file_set["id"]]
                else:
                    file_set_id_grouped_by_time_val[time_val][lot_id].append(file_set["id"])

        machine_initial_total_count = {}

        for time_val, meta_info in meta_info_grouped_by_time_val.items():
            scatter_result = []
            trend_result = []
            total_inspected = 0
            for info in meta_info:
                if info[0] and info[1]:
                    total_inspected += int(info[1])
                    try:
                        count = len(file_set_id_grouped_by_time_val[time_val][info[0]])
                    except KeyError:
                        count = 0
                    if not machine_initial_total_count.get(info[2], None):
                        machine_initial_total_count[info[2]] = [0, 0]
                    total_and_count = machine_initial_total_count[info[2]]
                    total_and_count[0] += count
                    total_and_count[1] += int(info[1])
                    try:
                        overkill_scatter_percentage = round(count * 100 / int(info[1]), 2)
                        scatter_result.append(
                            {
                                "machine_no": info[2],
                                "lot_id": info[0],
                                "percentage": overkill_scatter_percentage,
                                "over_reject_count": count,
                                "total_unit_count": int(info[1]),
                            }
                        )
                    except ZeroDivisionError:
                        overkill_scatter_percentage = None

            for scatter in scatter_result:
                machine_no = scatter["machine_no"]
                try:
                    idx = next(i for i, d in enumerate(trend_result) if machine_no in d.values())
                    trend_result[idx]["over_reject_count"] += scatter["over_reject_count"]
                    trend_result[idx]["total_unit_count"] += scatter["total_unit_count"]
                except StopIteration:
                    trend_result.append(
                        {
                            "machine_no": machine_no,
                            "over_reject_count": scatter["over_reject_count"],
                            "total_unit_count": scatter["total_unit_count"],
                        }
                    )

            for trend in trend_result:
                trend["percentage"] = round(trend["over_reject_count"] * 100 / trend["total_unit_count"], 2)

            time_str = time_val.strftime("%Y-%m-%d")
            if time_format == "monthly":
                year = time_val.year
                month = time_val.month
                last_date = monthrange(year, month)[1]
                time_str = f"{time_str} : {year}-{month}-{last_date}"
            elif time_format == "weekly":
                end_date = time_val + timedelta(days=7)
                time_str = f"{time_str} : {end_date.strftime('%Y-%m-%d')}"

            overkill_scatter_plot[time_str] = scatter_result
            overkill_trend[time_str] = trend_result

        modified_overkill_trend = []
        for date in overkill_trend:
            obj = {"date_range": date}
            for ele in overkill_trend[date]:
                obj[ele["machine_no"]] = {
                    "total_unit_count": ele["total_unit_count"],
                    "over_reject_count": ele["over_reject_count"],
                    "percentage": ele["percentage"],
                }
            modified_overkill_trend.append(obj)

        response = {
            "overkill_scatter": overkill_scatter_plot,
            "overkill_trend": modified_overkill_trend,
            "machine_wise_overkill_rate": {},
        }

        for machine, val in machine_initial_total_count.items():
            response["machine_wise_overkill_rate"][machine] = {
                "percentage": round(100 * val[0] / val[1], 2),
                "over_reject_count": val[0],
                "total_unit_count": val[1],
            }
        return Response(response)

    @action(
        detail=False,
        methods=["GET"],
    )
    def heatmap(self, request):
        heatmap_url = settings.HEATMAP_URL
        if not heatmap_url:
            return Response("Can't connect to the heatmap service", status=status.HTTP_503_SERVICE_UNAVAILABLE)
        feedback_flag = request.query_params.get("feedback_flag", False)
        percentage_cutoff = request.query_params.get("percentage_cutoff", "30,70").split(",")
        percentage_cutoff = list(map(int, percentage_cutoff))
        colour_map_1 = tuple(request.query_params.get("colour_map_1", "0,180,180").split(","))
        colour_map_1 = list(map(int, colour_map_1))
        colour_map_2 = tuple(request.query_params.get("colour_map_2", "0,140,255").split(","))
        colour_map_2 = list(map(int, colour_map_2))
        colour_map_3 = tuple(request.query_params.get("colour_map_3", "0,0,255").split(","))
        colour_map_3 = list(map(int, colour_map_3))
        colour_map = colour_map_1 + colour_map_2 + colour_map_3
        file_set_filters = {}
        ml_model_filters = {}
        filtered_defects = []
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "defect_id__in":
                filtered_defects = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            else:
                file_set_filters[key] = val.split(",")

        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        if filtered_defects:
            file_regions = analysis_service.file_regions().filter(defects__has_any_keys=filtered_defects)
        else:
            file_regions = analysis_service.file_regions()
        file_ids = file_regions.filter().values_list("file_id", flat=True)
        file_ids = ",".join(list(map(str, file_ids)))
        filtered_defects = list(map(int, filtered_defects))
        model_id = MlModel.objects.filter(code="top_lead", status="deployed_in_prod").first().id

        sys.path.append(settings.DS_MODEL_INVOCATION_PATH)
        logger.info(f"file_ids: {file_ids}")
        logger.info(f"filtered_defects: {filtered_defects}")
        logger.info(f"feedback_flag: {feedback_flag}")
        logger.info(f"percentage_cutoff: {percentage_cutoff}")
        logger.info(f"colour_map: {colour_map}")

        body = {
            "file_ids": file_ids,
            "feedback_flag": feedback_flag,
            "percentage_cutoff": percentage_cutoff,
            "colour_maps": colour_map,
            "model_id": model_id,
        }
        url = f"http://{heatmap_url}/"
        file_path = requests.post(url, json=body).json()
        logger.info(f"file_path: {file_path}")
        if file_path:
            file_storage = locate(settings.DEFAULT_FILE_STORAGE)()
            pre_signed_url = file_storage.url(file_path)
        else:
            pre_signed_url = None
        return Response({"pre_signed_url": pre_signed_url}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["GET"],
    )
    def lead_level_csv(self, request):
        lead_position_url = settings.LEAD_POSITION_URL
        if not lead_position_url:
            return Response("Can't connect to the lead level service", status=status.HTTP_503_SERVICE_UNAVAILABLE)
        file_set_filters = {}
        ml_model_filters = {}
        filtered_defects = []
        date__gte = settings.PROJECT_START_DATE
        date__lte = datetime.now()
        file_set_filters["created_ts__gte"] = date__gte
        file_set_filters["created_ts__lte"] = date__lte

        for key, val in request.query_params.items():
            if key == "ml_model_id__in":
                ml_model_filters["id__in"] = val.split(",")
            elif key == "subscription_id":
                file_set_filters["subscription_id__in"] = val.split(",")
            elif key == "defect_id__in":
                filtered_defects = val.split(",")
            elif key == "date__gte":
                file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            elif key == "date__lte":
                file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
            else:
                file_set_filters[key] = val.split(",")

        analysis_service = AnalysisService(file_set_filters, ml_model_filters)
        if filtered_defects:
            file_regions = analysis_service.file_regions().filter(defects__has_any_keys=filtered_defects)
        else:
            file_regions = analysis_service.file_regions()
        file_ids = file_regions.filter().values_list("file_id", flat=True)
        file_ids = ",".join(list(map(str, file_ids)))
        model_id = MlModel.objects.filter(code="top_lead", status="deployed_in_prod").first().id

        body = {
            "file_ids": file_ids,
            "model_id": model_id,
        }
        url = f"http://{lead_position_url}/"
        file_path = requests.post(url, json=body).json()
        logger.info(f"file_path: {file_path}")
        if file_path:
            file_storage = locate(settings.DEFAULT_FILE_STORAGE)()
            pre_signed_url = file_storage.url(file_path)
        else:
            pre_signed_url = None
        return Response({"pre_signed_url": pre_signed_url}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes((permissions.IsAuthenticated,))
def prediction_csv(request):
    file_set_filters = {}
    ml_model_filters = {}
    date__gte = datetime(2020, 7, 31, 0, 0, 0, tzinfo=pytz.UTC)
    date__lte = datetime.now()
    file_set_filters["created_ts__gte"] = date__gte
    file_set_filters["created_ts__lte"] = date__lte
    single_label_classification = True

    for key, val in request.query_params.items():
        if key == "ml_model_id__in":
            ml_model_filters["id__in"] = list(map(int, (val.split("-"))))
        elif key == "subscription_id":
            file_set_filters["subscription_id__in"] = val.split(",")
        elif key == "date__gte":
            file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        elif key == "date__lte":
            file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        else:
            file_set_filters[key] = val.split(",")

    ml_model_map = {}
    for model in MlModel.objects.filter(id__in=ml_model_filters["id__in"]).prefetch_related("use_case"):
        if model.classification_type != "SINGLE_LABEL":
            single_label_classification = False
        ml_model_map[model.id] = model.name
    upload_session_ids = file_set_filters["upload_session_id__in"]
    upload_session_names = list(
        UploadSession.objects.filter(id__in=list(map(int, upload_session_ids))).values_list("name", flat=True)
    )

    analysis_service = AnalysisService(file_set_filters, ml_model_filters)
    # files = analysis_service.files().prefetch_related(Prefetch("file_regions", queryset=
    # FileRegion.objects.filter(ml_model_id__in=list(ml_model_map.keys()))))

    temp_csv = tempfile.NamedTemporaryFile()
    with open(temp_csv.name, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            ["File", "Folder", "Coordinates", "AI Predictions", "Ground Truth", "Model", "InferenceStatus"]
        )
        defect_name_map = {}
        for defect in Defect.objects.all():
            defect_name_map[defect.id] = defect.name

        all_file_sets = analysis_service.file_sets().prefetch_related("files", "files__file_regions", "upload_session")
        queue_items = FileSetInferenceQueue.objects.filter(
            file_set__in=all_file_sets, ml_model_id__in=ml_model_filters["id__in"]
        ).order_by("created_ts")

        model_file_set_task_map = {}
        for item in queue_items:
            if not model_file_set_task_map.get(item.ml_model_id, None):
                model_file_set_task_map[item.ml_model_id] = {item.file_set_id: [item]}
            else:
                if not model_file_set_task_map[item.ml_model_id].get(item.file_set_id, None):
                    model_file_set_task_map[item.ml_model_id][item.file_set_id] = [item]
                else:
                    model_file_set_task_map[item.ml_model_id][item.file_set_id].append(item)

        for file_set in all_file_sets:
            ai_defects_slc = []
            gt_defects_slc = []
            for file in file_set.files.all():
                if not file.file_regions.all():
                    item = file_set.file_set_inference_queues.filter(ml_model_id__in=ml_model_filters["id__in"]).last()
                    if item:
                        model_id = item.ml_model_id
                        model_name = ml_model_map[model_id]
                        inference_status = item.status
                        writer.writerow(
                            [file.name, file_set.upload_session.name, None, None, None, model_name, inference_status]
                        )
                        continue
                for region in file.file_regions.all():
                    ai_defects = []
                    gt_defects = []
                    if region.ml_model_id in ml_model_filters["id__in"]:
                        if region.is_user_feedback is False:
                            for defect_id in region.defects:
                                defect_name = defect_name_map[int(defect_id)]
                                ai_defects_slc.append(defect_name)
                                ai_defects.append(defect_name)
                                if (
                                    region.is_removed is False
                                    and (
                                        region.detection_correctness is True
                                        or region.classification_correctness is True
                                    )
                                    and region.file_regions.count() == 0
                                ):
                                    gt_defects_slc.append(defect_name)
                                    gt_defects.append(defect_name)
                        else:
                            if region.is_removed is False:
                                for defect_id in region.defects:
                                    defect_name = defect_name_map[int(defect_id)]
                                    gt_defects_slc.append(defect_name)
                                    gt_defects.append(defect_name)
                        coordinates = region.region
                        ai_defects = ";".join(ai_defects)
                        gt_defects = ";".join(gt_defects)
                        try:
                            items = model_file_set_task_map[region.ml_model_id][file_set.id]
                            inference_status = items[-1].status
                            model_name = ml_model_map[region.ml_model_id]
                            if not single_label_classification:
                                writer.writerow(
                                    [
                                        file.name,
                                        file_set.upload_session.name,
                                        coordinates,
                                        ai_defects,
                                        gt_defects,
                                        model_name,
                                        inference_status,
                                    ]
                                )
                        except KeyError:
                            continue
                if single_label_classification:
                    ai_defects_joined = ";".join(ai_defects_slc)
                    gt_defects_joined = ";".join(gt_defects_slc)
                    writer.writerow(
                        [
                            file.name,
                            file_set.upload_session.name,
                            None,
                            ai_defects_joined,
                            gt_defects_joined,
                            model_name,
                            inference_status,
                        ]
                    )

    FilePointer = open(temp_csv.name, "r")
    response = HttpResponse(FilePointer, content_type="application/csv")
    file_name = "-".join(upload_session_names)
    response["Content-Disposition"] = f"attachment; file_name={file_name}.csv"
    response["Access-Control-Expose-Headers"] = "Content-Disposition"

    return response


@api_view(["GET"])
@permission_classes((permissions.IsAuthenticated,))
def ai_results_csv(request):
    file_set_filters = {}
    ml_model_filters = {}
    date__gte = settings.PROJECT_START_DATE
    date__lte = datetime.now()
    file_set_filters["created_ts__gte"] = date__gte
    file_set_filters["created_ts__lte"] = date__lte
    subscription_id = None

    for key, val in request.query_params.items():
        if key == "ml_model_id__in":
            ml_model_filters["id__in"] = val.split(",")
        elif key == "subscription_id":
            file_set_filters["subscription_id__in"] = val.split(",")
            subscription_id = val
        elif key == "date__gte":
            file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        elif key == "date__lte":
            file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        else:
            file_set_filters[key] = val.split(",")
    analysis_service = AnalysisService(file_set_filters, ml_model_filters)

    ordered_defect_ids = get_env().list("ORDERED_DEFECT_IDS", cast=int, default=[1, 2, 4, 5, 3, 6])
    defect_ordering_cases = []
    for idx, defect_id in enumerate(ordered_defect_ids):
        defect_ordering_cases.append(When(id=defect_id, then=Value(idx)))
    defect_ordering_cases.append(When(~Q(id__in=ordered_defect_ids), then=Value(100000)))
    ordered_defects = list(
        Defect.objects.annotate(
            custom_order=Case(
                *defect_ordering_cases,
                output_field=IntegerField(),
            )
        )
        .order_by("custom_order")
        .values_list("id", "name")
    )
    ordered_defect_ids = [defect[0] for defect in ordered_defects]
    ordered_defect_names = [defect[1] for defect in ordered_defects]
    file_set_meta_info = Subscription.objects.get(id=subscription_id).file_set_meta_info
    meta_info_args = [f"meta_info__{item['field']}" for item in file_set_meta_info]
    meta_info_headings = [item["field"] for item in file_set_meta_info]

    file_sets = (
        FileSet.objects.filter(files__file_regions__in=analysis_service.ai_regions())
        .values("id", *meta_info_args)
        .distinct()
        .annotate(defects=JSONBAgg("files__file_regions__defects"))
    )
    file_set_lot_id_count = (
        analysis_service.file_sets().values("meta_info__lot_id").annotate(count=Count("id", distinct=True))
    )
    # file_set_lot_id_count = FileSet.objects.filter(
    #     files__file_regions__in=analysis_service.ai_regions()
    # ).values('meta_info__lot_id').annotate(count=Count('id', distinct=True))
    meta_info_rows = {}

    for file_set in file_sets:
        lot_id = file_set["meta_info__lot_id"]
        defects = file_set.pop("defects")
        file_set.pop("id")
        defect_ids = [defect_id for defect in defects for defect_id in defect]
        defect_ids = list(map(int, defect_ids))
        # if all_meta_uniq_el not in meta_info_rows:
        if lot_id not in meta_info_rows:
            val = list(file_set.values())
            try:
                count = next(item for item in file_set_lot_id_count if lot_id in item.values())["count"]
                val.append(count)
            except StopIteration:
                continue
            val.extend([0] * len(ordered_defect_ids))
            meta_info_rows[lot_id] = val
            for order_defect_id in ordered_defect_ids:
                for defect_id in defect_ids:
                    if defect_id == order_defect_id:
                        idx = ordered_defect_ids.index(defect_id)
                        row = meta_info_rows[lot_id]
                        row[len(file_set) + idx + 1] = 1
                        meta_info_rows[lot_id] = row
                        break
                else:
                    continue
                break
        else:
            row = meta_info_rows[lot_id]
            # row_arr = row[0].split(',')
            for idx, el in enumerate(row):
                if idx < len(list(file_set.values())):
                    if el is None:
                        pp = []
                    else:
                        pp = str(el).split(";;")

                    new_pp = list(file_set.values())[idx]
                    if new_pp is None:
                        new_pp = "None"
                    pp.append(new_pp)
                    pp = list(map(str, set(pp)))
                    row[idx] = ";;".join(pp)
            meta_info_rows[lot_id] = row
            for order_defect_id in ordered_defect_ids:
                for defect_id in defect_ids:
                    if defect_id == order_defect_id:
                        idx = ordered_defect_ids.index(defect_id)
                        row[len(file_set) + idx + 1] += 1
                        meta_info_rows[lot_id] = row
                        break
                else:
                    continue
                break

    temp_csv = tempfile.NamedTemporaryFile()
    with open(temp_csv.name, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        heading_row = [*meta_info_headings, "No. of records received by the platform", *ordered_defect_names]
        writer.writerow(heading_row)
        for row in meta_info_rows.values():
            writer.writerow(row)

    FilePointer = open(temp_csv.name, "r")
    response = HttpResponse(FilePointer, content_type="application/csv")
    file_name = "ai_results"  # ToDo: Rename to something more sensible.
    response["Content-Disposition"] = f"attachment; file_name={file_name}.csv"
    response["Access-Control-Expose-Headers"] = "Content-Disposition"

    return response
