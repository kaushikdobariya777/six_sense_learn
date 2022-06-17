# these classes could be separated into files and put inside a metrics folder
from typing import Dict, List
from django.db.models.aggregates import Count, Sum
from django.db.models.expressions import F, ExpressionWrapper
from django.db.models.fields import BooleanField, FloatField
from django.db.models.functions import Cast, Concat, Round
from django.db.models.functions.comparison import Coalesce, NullIf
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from rest_framework.exceptions import ValidationError

from django.db import connection


class ClasswiseMetrics:
    @staticmethod
    def defect_level(input_queryset: QuerySet) -> List[Dict]:
        output = {}
        for row in input_queryset:
            gt_defect_id = row.get("gt_defect_id")
            model_defect_id = row.get("model_defect_id")
            if output.get(gt_defect_id) is None:
                output[gt_defect_id] = {
                    "gt_defect_id": gt_defect_id,
                    "gt_defect_name": row.get("gt_defect_name"),
                    "accurate": 0,
                    "auto_classified": 0,
                    "missed": 0,
                    "extra": 0,
                    "total": 0,
                    "total_gt_defects": 0,
                    "total_model_defects": 0,
                }
            if output.get(model_defect_id) is None:
                output[model_defect_id] = {
                    "gt_defect_id": model_defect_id,
                    "gt_defect_name": row.get("model_defect_name"),
                    "accurate": 0,
                    "auto_classified": 0,
                    "missed": 0,
                    "extra": 0,
                    "total": 0,
                    "total_gt_defects": 0,
                    "total_model_defects": 0,
                }
            if row.get("confidence_threshold") is None:
                raise ValidationError("confidence_threshold not found for {}".format(row.get("ml_model_name")))
            # TODO: case where gt defect is there and model defect is not confident will not be treated as missed. ask about this?
            # auto-classified defects
            auto_classified = row.get("confidence") is not None and row.get("confidence") >= row.get(
                "confidence_threshold"
            )
            output.get(gt_defect_id)["total"] = output.get(gt_defect_id).get("total", 0) + 1
            # true positives
            if auto_classified:
                output.get(gt_defect_id)["auto_classified"] = output.get(gt_defect_id).get("auto_classified", 0) + 1
                if gt_defect_id is not None:
                    output.get(gt_defect_id)["total_gt_defects"] = (
                        output.get(gt_defect_id).get("total_gt_defects", 0) + 1
                    )
                if model_defect_id is not None:
                    output.get(model_defect_id)["total_model_defects"] = (
                        output.get(model_defect_id).get("total_model_defects", 0) + 1
                    )
                if gt_defect_id == model_defect_id:
                    output.get(gt_defect_id)["accurate"] = output.get(gt_defect_id).get("accurate", 0) + 1
                else:
                    # false negatives
                    output.get(gt_defect_id)["missed"] = output.get(gt_defect_id).get("missed", 0) + 1
                    # false positives
                    output.get(model_defect_id)["extra"] = output.get(model_defect_id).get("extra", 0) + 1

            # auto-classified percentage
            if output.get(gt_defect_id).get("total") > 0:
                output.get(gt_defect_id)["auto_classified_percentage"] = round(
                    100 * output.get(gt_defect_id).get("auto_classified", 0) / output.get(gt_defect_id).get("total"), 0
                )
            # accuracy percentage only when thhre is auto classified defects
            if output.get(gt_defect_id).get("auto_classified", 0) > 0:
                output.get(gt_defect_id)["accuracy_percentage"] = round(
                    100
                    * output.get(gt_defect_id).get("accurate", 0)
                    / output.get(gt_defect_id).get("auto_classified"),
                    0,
                )
                output.get(gt_defect_id)["missed_percentage"] = round(
                    100 * output.get(gt_defect_id).get("missed", 0) / output.get(gt_defect_id).get("auto_classified"),
                    0,
                )
            model_predicted = output.get(gt_defect_id).get("extra") + output.get(gt_defect_id).get("accurate")
            if model_predicted > 0:
                output.get(gt_defect_id)["extra_percentage"] = round(
                    100 * output.get(gt_defect_id).get("extra", 0) / model_predicted, 0
                )
            if output.get(gt_defect_id).get("total_gt_defects") > 0:
                output.get(gt_defect_id)["recall_percentage"] = round(
                    100
                    * output.get(gt_defect_id).get("accurate", 0)
                    / output.get(gt_defect_id).get("total_gt_defects"),
                    0,
                )
            if output.get(gt_defect_id).get("total_model_defects") > 0:
                output.get(gt_defect_id)["precision_percentage"] = round(
                    100
                    * output.get(gt_defect_id).get("accurate", 0)
                    / output.get(gt_defect_id).get("total_model_defects"),
                    0,
                )
        # TODO: change back return type to dictionary after talking with frontend team
        if output.get(None) is not None:
            del output[None]
        return list(output.values())

    @staticmethod
    def use_case_level(input_queryset: QuerySet) -> List[Dict]:
        """[classwise data at use case level]

        Args:
            input_queryset ([type]): [description]

        Returns:
            [type]: [description]
        """
        # Original django ORM code for reference.
        # can't do the query in ORM as of now, since it does not support aggregate after window clause

        # aggregated_query = {
        #     "total": Count("gt_defect_id"),
        #     "auto_classified": Count("gt_defect_id", filter=Q(confidence_threshold__lte=F("confidence"))),
        #     "auto_classified_percentage": (
        #         100 * Count("gt_defect_id", filter=Q(confidence_threshold__lte=F("confidence")))
        #     )
        #     / NullIf(Count("gt_defect_id"), 0),
        #     "accurate": Count(
        #         "gt_defect_id", filter=Q(confidence_threshold__lte=F("confidence"), gt_defect_id=F("model_defect_id"))
        #     ),
        #     "accuracy_percentage": (
        #         100
        #         * Count(
        #             "gt_defect_id",
        #             filter=Q(confidence_threshold__lte=F("confidence"), gt_defect_id=F("model_defect_id")),
        #         )
        #     )
        #     / NullIf(Count("gt_defect_id", filter=Q(confidence_threshold__lte=F("confidence"))), 0),
        # }
        # return input_queryset.values("use_case_id", "use_case_name").annotate(**aggregated_query)

        sql, params = input_queryset.query.sql_with_params()
        output_sql = """
            select 
                use_case_id,
                use_case_name,
                count(*) as total,
                count(*) filter(where confidence_threshold <= confidence) as auto_classified,
                round(100*(count(*) filter(where confidence_threshold <= confidence)) / nullif(count(*), 0), 0) as auto_classified_percentage, 
                count(*) filter(where confidence_threshold <= confidence and gt_defect_id = model_defect_id) as accurate,
                round(100*(count(*) filter(where confidence_threshold <= confidence and gt_defect_id = model_defect_id)) / nullif(count(*) filter(where confidence_threshold <= confidence), 0), 0) as accuracy_percentage,
                sum(count(*)) over() as total_defects,
                round((100*(count(*) - count(*) filter(where confidence_threshold <= confidence)) / nullif(sum(count(*)) over(), 0)), 0) as auto_classification_drop,
                sum(count(*) filter(where confidence_threshold <= confidence)) over() as total_auto_classified,
                round((100*(count(*) filter(where confidence_threshold <= confidence) - count(*) filter(where confidence_threshold <= confidence and gt_defect_id = model_defect_id)) / nullif(sum(count(*) filter(where confidence_threshold <= confidence)) over(), 0)), 0) as accuracy_drop
            from ({}) "table"
            group by use_case_id, use_case_name
        """.format(
            sql
        )

        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            return CommonMetrics.dictfetchall(cursor)


class ConfusionMatrix:
    @staticmethod
    def confusion_matrix(input_queryset: QuerySet) -> Dict:
        # TODO: left join ??? gt has defect but model does not?
        sql, params = input_queryset.query.sql_with_params()
        output_sql = """
            select 
                coalesce(gt_defect_id, -1) as gt_defect_id,
                model_defect_id,
                coalesce(gt_defect_name, 'unknown') as gt_defect_name,
                model_defect_name,
                replace(gt_defect_organization_code, 'N/A', '') as gt_defect_organization_code,
                replace(model_defect_organization_code, 'N/A', '') as model_defect_organization_code,
                count(*) as paired_count, 
                sum(count(*)) over( partition by gt_defect_id) as gt_count,
                sum(count(*)) over( partition by model_defect_id) as model_count,
                sum(count(*)) filter(where gt_defect_id <> model_defect_id) over(order by count(*) desc, gt_defect_id, model_defect_id ) as cumulative_sum,
                sum(count(*)) filter(where gt_defect_id <> model_defect_id) over() as total_missclassifications,
                sum(count(*)) over() as total
            from ({}) "table"
            group by gt_defect_id, model_defect_id, gt_defect_name, model_defect_name, gt_defect_organization_code, model_defect_organization_code
            order by count(*) desc	
        """.format(
            sql
        )
        output = {}
        ranking_list = [0.5, 0.7, 1]
        ranking_index = 0
        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            columns = [col[0] for col in cursor.description]
            for row in cursor.fetchall():
                zipped = dict(zip(columns, row))
                if output.get(zipped.get("gt_defect_id")) is None:
                    output.update(
                        {
                            zipped.get("gt_defect_id"): {
                                "model_defects": {
                                    zipped.get("model_defect_id"): {
                                        "matched_count": zipped.get("paired_count"),
                                        "defect": {
                                            "id": zipped.get("model_defect_id"),
                                            "name": zipped.get("model_defect_name"),
                                            "organization_defect_code": zipped.get("model_defect_organization_code"),
                                            "display": (
                                                zipped.get("model_defect_organization_code")
                                                + " "
                                                + zipped.get("model_defect_name")
                                            ).lstrip(),
                                        },
                                    }
                                },
                                "gt_count": zipped.get("gt_count"),
                                "model_count": 0,
                                "defect": {
                                    "id": zipped.get("gt_defect_id"),
                                    "name": zipped.get("gt_defect_name"),
                                    "organization_defect_code": zipped.get("gt_defect_organization_code"),
                                    "display": (
                                        zipped.get("gt_defect_organization_code") + " " + zipped.get("gt_defect_name")
                                    ).lstrip(),
                                },
                                "recall": None,
                            }
                        }
                    )
                else:
                    output.get(zipped.get("gt_defect_id")).update(
                        {
                            "gt_count": zipped.get("gt_count"),
                            "defect": {
                                "id": zipped.get("gt_defect_id"),
                                "name": zipped.get("gt_defect_name"),
                                "organization_defect_code": zipped.get("gt_defect_organization_code"),
                                "display": (
                                    zipped.get("gt_defect_organization_code") + " " + zipped.get("gt_defect_name")
                                ).lstrip(),
                            },
                        }
                    )
                    output.get(zipped.get("gt_defect_id")).get("model_defects").update(
                        {
                            zipped.get("model_defect_id"): {
                                "matched_count": zipped.get("paired_count"),
                                "defect": {
                                    "id": zipped.get("model_defect_id"),
                                    "name": zipped.get("model_defect_name"),
                                    "organization_defect_code": zipped.get("model_defect_organization_code"),
                                    "display": (
                                        zipped.get("model_defect_organization_code")
                                        + " "
                                        + zipped.get("model_defect_name")
                                    ).lstrip(),
                                },
                            }
                        }
                    )
                if output.get(zipped.get("model_defect_id")) is None:
                    output.update(
                        {
                            zipped.get("model_defect_id"): {
                                "model_defects": {},
                                "model_count": zipped.get("model_count"),
                                "defect": {
                                    "id": zipped.get("model_defect_id"),
                                    "name": zipped.get("model_defect_name"),
                                    "organization_defect_code": zipped.get("model_defect_organization_code"),
                                    "display": (
                                        zipped.get("model_defect_organization_code")
                                        + " "
                                        + zipped.get("model_defect_name")
                                    ).lstrip(),
                                },
                                "gt_count": 0,
                                "recall": None,
                            }
                        }
                    )
                else:
                    output.get(zipped.get("model_defect_id")).update({"model_count": zipped.get("model_count")})

                if zipped.get("gt_defect_id") == zipped.get("model_defect_id"):
                    output.get(zipped.get("gt_defect_id")).update(
                        {
                            "accurate_defect_count": zipped.get("paired_count"),
                            "recall": round(
                                100
                                * zipped.get("paired_count")
                                / output.get(zipped.get("gt_defect_id")).get("gt_count"),
                                0,
                            ),
                            "precision": round(
                                100
                                * zipped.get("paired_count")
                                / output.get(zipped.get("gt_defect_id")).get("model_count"),
                                0,
                            ),
                        }
                    )
                else:
                    if zipped.get("cumulative_sum") is None:
                        zipped["cumulative_sum"] = 0
                    percentile = zipped.get("cumulative_sum", 0) / zipped.get("total_missclassifications")
                    if not percentile <= ranking_list[ranking_index]:
                        ranking_index = ranking_index + 1
                    output.get(zipped.get("gt_defect_id")).get("model_defects").get(
                        zipped.get("model_defect_id")
                    ).update({"rank": ranking_index, "rank_percentile": round(percentile, 0)})
        return output


class CommonMetrics:
    # TODO: send method to a common place
    @staticmethod
    def dictfetchall(cursor) -> List[Dict]:
        """Return all rows from a cursor as a dict"""
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def missclassification_defect_level(input_queryset: QuerySet) -> List[Dict]:
        sub_query = input_queryset.filter(~Q(gt_defect_id=F("model_defect_id"))).query
        sql, params = sub_query.sql_with_params()
        output = """
            SELECT gt_defect_id, 
            model_defect_id,
            gt_defect_name,
            model_defect_name,
            count(*) as miss_classifications,
            sum(count(*)) over() as total_miss_classifications,
            round(100*count(*)/(sum(count(*)) over()),0) as miss_classification_percentage
            FROM ({}) "table"
            group by gt_defect_id, model_defect_id, gt_defect_name, model_defect_name
            order by count(*) desc
            """.format(
            sql
        )
        with connection.cursor() as cursor:
            cursor.execute(output, params)
            return CommonMetrics.dictfetchall(cursor)


class AccuracyMetrics:
    @staticmethod
    def defect_level(input_queryset: QuerySet) -> Dict:
        """[calculated accuracy metrics on defects, defects that match are divided by gt defects]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id' and 'model_defect_id']
        Returns:
            [dict]: [returns total defects and matched defects]
        """
        aggregated_query = {
            "total": Count(Concat("gt_defect_id", "file_id"), distinct=True),
            "accurate": Count(
                Concat("model_defect_id", "file_id"), distinct=True, filter=Q(gt_defect_id=F("model_defect_id"))
            ),
            "percentage": (
                100
                * Count(
                    Concat("model_defect_id", "file_id"), distinct=True, filter=Q(gt_defect_id=F("model_defect_id"))
                )
            )
            / NullIf(Count(Concat("gt_defect_id", "file_id"), distinct=True), 0),
        }
        return input_queryset.aggregate(**aggregated_query)

    @staticmethod
    def defect_level_timeseries(input_queryset: QuerySet) -> List[Dict]:
        """[ calculates accuracy metrics in timeseries on defects, defects that match are divided by gt defects]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id' and 'model_defect_id', 'effective_date']
        Returns:
            [dict]: [returns total defects and matched defects for each date]
        """
        aggregated_query = {
            "total": Count(Concat("gt_defect_id", "file_id"), distinct=True),
            "accurate": Count(
                Concat("model_defect_id", "file_id"), distinct=True, filter=Q(gt_defect_id=F("model_defect_id"))
            ),
            "percentage": (
                100
                * Count(
                    Concat("model_defect_id", "file_id"), distinct=True, filter=Q(gt_defect_id=F("model_defect_id"))
                )
            )
            / NullIf(Count(Concat("gt_defect_id", "file_id"), distinct=True), 0),
        }
        return input_queryset.values("effective_date").annotate(**aggregated_query)

    @staticmethod
    def wafer_level(input_queryset: QuerySet) -> Dict:
        """[calculates accuracy metrics on wafers, each usecase has a wafer threshold]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id' and 'model_defect_id']
        Returns:
            [dict]: [returns total wafers and accurate wafers]
        """
        aggregated_query = {
            "wafer_accuracy": Cast(
                100 * Count("model_defect_id", filter=Q(gt_defect_id=F("model_defect_id"))), FloatField()
            )
            / Count("gt_defect_id"),
            "wafer_accuracy_total": Count("model_defect_id", filter=Q(gt_defect_id=F("model_defect_id"))),
            "wafer_total": Count("model_defect_id"),
        }
        wafer_aggregated_query = {
            "total": Coalesce(Sum("wafer_total", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))), 0),
            "accurate": Coalesce(Sum("wafer_accuracy_total", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))), 0),
            "percentage": (100 * Sum("wafer_accuracy_total", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))))
            / NullIf(Sum("wafer_total", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))), 0),
        }
        return (
            input_queryset.values("wafer_id", "wafer_threshold")
            .annotate(**aggregated_query)
            .aggregate(**wafer_aggregated_query)
        )

    @staticmethod
    def wafer_level_timeseries(input_queryset: QuerySet) -> List[Dict]:
        """[calculates timeseries accuracy metrics on wafers, each usecase has a wafer threshold]
        Args:
            input_queryset ([QuerySet])
        Returns:
            [dict]: [returns total wafers and accurate wafers]
        """
        aggregated_query = {
            "wafer_accuracy": Cast(
                100 * Count("model_defect_id", filter=Q(gt_defect_id=F("model_defect_id"))), FloatField()
            )
            / Count("gt_defect_id"),
            "wafer_accuracy_total": Count("model_defect_id", filter=Q(gt_defect_id=F("model_defect_id"))),
            "wafer_total": Count("model_defect_id"),
        }
        sql, params = (
            input_queryset.values("wafer_id", "wafer_threshold", "effective_date")
            .annotate(**aggregated_query)
            .query.sql_with_params()
        )
        output_sql = """
            SELECT effective_date, \
            coalesce(sum(wafer_total) filter (where wafer_accuracy>=wafer_threshold), 0)  as total, \
            coalesce(sum(wafer_accuracy_total) filter (where wafer_accuracy>=wafer_threshold), 0) as accurate, \
            (100*(sum(wafer_accuracy_total) filter (where wafer_accuracy>=wafer_threshold))) / nullif(sum(wafer_total) filter (where wafer_accuracy>=wafer_threshold) ,0) as percentage \
            FROM ({}) "table" \
            group by effective_date \
            order by effective_date
        """.format(
            sql
        )
        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            return CommonMetrics.dictfetchall(cursor)


class AutoClassificationMetrics:
    @staticmethod
    def defect_level(input_queryset: QuerySet) -> Dict:
        """[calculated autoclassification metrics on defects]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id', 'confidence' and 'confidence_threshold']
        Returns:
            [dict]: [returns total defects and autoclassified defects]
        """
        aggregated_query = {
            "total": Count("file_id"),
            "auto_classified": Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))),
            "percentage": (100 * Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))))
            / NullIf(Count("file_id"), 0),
        }
        return input_queryset.aggregate(**aggregated_query)

    @staticmethod
    def defect_level_timeseries(input_queryset: QuerySet) -> List[Dict]:
        """[calculated autoclassification metrics in timeseries of defects]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id', 'effective_date', 'confidence' and 'confidence_threshold']
        Returns:
            [dict]: [returns total defects and autoclassified defects]
        """
        aggregated_query = {
            "total": Count("gt_defect_id"),
            "auto_classified": Count("gt_defect_id", filter=Q(confidence_threshold__lte=F("confidence"))),
            "percentage": (100 * Count("gt_defect_id", filter=Q(confidence_threshold__lte=F("confidence"))))
            / NullIf(Count("gt_defect_id"), 0),
        }
        return input_queryset.values("effective_date").annotate(**aggregated_query)

    @staticmethod
    def defect_distribution(input_queryset: QuerySet) -> List[Dict]:
        sql, params = input_queryset.annotate(
            matched=ExpressionWrapper(Q(confidence_threshold__lte=F("confidence")), output_field=BooleanField())
        ).query.sql_with_params()

        output_sql = '\
            SELECT gt_defect_id as defect_id, \
            cast(sum(count(*)) over () as int) as total, \
            count(*) as defects, \
            count(*) filter (where matched=true) as auto_classified\
            FROM ({}) "table" \
            group by gt_defect_id'.format(
            sql
        )

        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            return CommonMetrics.dictfetchall(cursor)

    @staticmethod
    def wafer_level(input_queryset: QuerySet) -> Dict:
        """[calculates autoclassification metrics on wafers, each usecase has a wafer threshold]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id' and 'model_defect_id']
        Returns:
            [dict]: [returns total wafers and accurate wafers]
        """
        aggregated_query = {
            "wafer_accuracy": Cast(
                100 * Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))), FloatField()
            )
            / NullIf(Count("file_id"), 0)
        }
        wafer_aggregated_query = {
            "total": Count("wafer_id"),
            "auto_classified": Count("wafer_id", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))),
            "manual": Count("wafer_id") - Count("wafer_id", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))),
            "percentage": (100 * Count("wafer_id", filter=Q(wafer_accuracy__gte=F("wafer_threshold"))))
            / NullIf(Count("wafer_id"), 0),
            "on_hold": Count("wafer_id", filter=Q(wafer_status="manual_classification_pending")),
        }
        return (
            input_queryset.values("wafer_id", "wafer_threshold")
            .annotate(**aggregated_query)
            .aggregate(**wafer_aggregated_query)
        )

    @staticmethod
    def wafer_level_timeseries(input_queryset: QuerySet) -> List[Dict]:
        """[calculates timeseries autoclassification metrics on wafers, each usecase has a wafer threshold]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'gt_defect_id' and 'model_defect_id']
        Returns:
            [dict]: [returns total wafers and accurate wafers]
        """
        aggregated_query = {
            "wafer_accuracy": Cast(
                100 * Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))), FloatField()
            )
            / Count("file_id")
        }
        sql, params = (
            input_queryset.values("wafer_id", "wafer_threshold", "effective_date")
            .annotate(**aggregated_query)
            .query.sql_with_params()
        )
        output_sql = """
            SELECT effective_date, \
            count(*) as total, \
            count(*) filter (where wafer_accuracy>=wafer_threshold) as auto_classified, \
            count(*) - count(*) filter (where wafer_accuracy>=wafer_threshold) as manual, \
            (100*(count(*) filter (where wafer_accuracy>=wafer_threshold)))/nullif(count(*),0) as percentage \
            FROM ({}) "table" \
            group by effective_date
            order by effective_date
        """.format(
            sql
        )

        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            return CommonMetrics.dictfetchall(cursor)

    @staticmethod
    def file_level(input_queryset: QuerySet) -> Dict:
        """[calculated autoclassification metrics on file, one confident defect means that the file is auto-classified]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'model_defect_id', 'confidence' and 'confidence_threshold']
        Returns:
            [dict]: [returns total defects and autoclassified defects]
        """
        annotated_query = {
            "auto_classified_defects_count": Count(
                "model_defect_id", filter=Q(confidence_threshold__lte=F("confidence"))
            )
        }
        aggregated_query = {
            "total": Count("file_id"),
            "auto_classified": Count("file_id", filter=Q(auto_classified_defects_count__gt=0)),
            "manual": Count("file_id") - Count("file_id", filter=Q(auto_classified_defects_count__gt=0)),
            "percentage": (100 * Count("file_id", filter=Q(auto_classified_defects_count__gt=0)))
            / NullIf(Count("file_id"), 0),
        }
        return input_queryset.values("file_id").annotate(**annotated_query).aggregate(**aggregated_query)

    @staticmethod
    def file_level_timeseries(input_queryset: QuerySet) -> List[Dict]:
        """[calculated autoclassification metrics per day, one confident defect means that a file is auto-classified]
        Args:
            input_queryset ([QuerySet]): [should send 'file_id', 'model_defect_id', 'effective_date', 'confidence' and 'confidence_threshold']
        Returns:
            [dict]: [returns total defects and autoclassified defects]
        """
        annotated_query = {
            "auto_classified_defects_count": Count(
                "model_defect_id", filter=Q(confidence_threshold__lte=F("confidence"))
            )
        }
        sql, params = (
            input_queryset.values("effective_date", "file_id").annotate(**annotated_query).query.sql_with_params()
        )
        output_sql = """
            SELECT effective_date, \
            count(file_id) as total, \
            count(file_id) filter (where auto_classified_defects_count>0) as auto_classified, \
            count(file_id) - count(file_id) filter (where auto_classified_defects_count>0) as manual, \
            (100*(count(file_id) filter (where auto_classified_defects_count>0)))/nullif(count(file_id),0) as percentage \
            FROM ({}) "table" \
            group by effective_date
            order by effective_date
        """.format(
            sql
        )

        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            return CommonMetrics.dictfetchall(cursor)


class DistributionMetrics:
    @staticmethod
    def file_distribution(
        input_queryset: QuerySet, group_by=None, order_by=None, order=None, nulls_first=True
    ) -> List[Dict]:
        """one method to calculate distribution on file level"""
        aggregated_query = {
            "total": Count("file_id"),
            "auto_classified": Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))),
            "manual": Count("file_id") - Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))),
            "auto_classified_percentage": Round(
                (100 * Cast(Count("file_id", filter=Q(confidence_threshold__lte=F("confidence"))), FloatField()))
                / NullIf(Count("file_id"), 0)
            ),
            "audited": Count(
                "file_id", filter=Q(confidence_threshold__lte=F("confidence"), gt_classification__isnull=False)
            ),
            "accurate": Count(
                "file_id",
                filter=Q(
                    confidence_threshold__lte=F("confidence"),
                    gt_classification__isnull=False,
                    gt_defect_id=F("model_defect_id"),
                ),
            ),
            "inaccurate": Count(
                "file_id", filter=Q(confidence_threshold__lte=F("confidence"), gt_classification__isnull=False)
            )
            - Count(
                "file_id",
                filter=Q(
                    confidence_threshold__lte=F("confidence"),
                    gt_classification__isnull=False,
                    gt_defect_id=F("model_defect_id"),
                ),
            ),
            "accuracy_percentage": Round(
                (
                    100
                    * Cast(
                        Count(
                            "file_id",
                            filter=Q(
                                confidence_threshold__lte=F("confidence"),
                                gt_classification__isnull=False,
                                gt_defect_id=F("model_defect_id"),
                            ),
                        ),
                        FloatField(),
                    )
                )
                / NullIf(
                    Count(
                        "file_id", filter=Q(confidence_threshold__lte=F("confidence"), gt_classification__isnull=False)
                    ),
                    0,
                )
            ),
        }
        if group_by is not None:
            input_queryset = input_queryset.values(*group_by).annotate(**aggregated_query)
        else:
            input_queryset = input_queryset.aggregate(**aggregated_query)
        if order_by is not None:
            if order is not None and order == "desc":
                # F will not work for multiple fields
                # it should be order_by(F('field1'), 'field2')
                if nulls_first:
                    input_queryset = input_queryset.order_by(F(*order_by).desc(nulls_first=nulls_first))
                else:
                    input_queryset = input_queryset.order_by(F(*order_by).desc())
            elif order is not None and order == "asc":
                input_queryset = input_queryset.order_by(F(*order_by).asc(nulls_first=nulls_first))
            else:
                input_queryset = input_queryset.order_by(*order_by)
        return input_queryset

    @staticmethod
    def use_case_on_wafer(input_queryset: QuerySet, execute=True):
        sql, params = input_queryset.query.sql_with_params()
        output_sql = '\
            SELECT use_case_id, use_case_name, ml_model_id, ml_model_name,\
            count(wafer_id) as total, \
            count(wafer_id) filter (where audited>0) as audited, \
            count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold) as auto_classified, \
            count(wafer_id) - count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold) as manual, \
            round(100*(count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold))/nullif(count(wafer_id), 0), 0) as auto_classified_percentage, \
            count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold and accuracy_percentage >= 90) as successful, \
            round ( 100 * count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold and accuracy_percentage >= 90) / nullif(count(wafer_id), 0), 0) as successful_percentage, \
            sum(total) as total_files, \
            sum(auto_classified) as auto_classified_files, \
            sum(audited) as audited_files, \
            sum(accurate) as accurate_files, \
            sum(audited) - sum(accurate) as inaccurate_files, \
            round(100*sum(accurate)/nullif(sum(audited), 0), 0) as accuracy_percentage_files, \
            round(100*sum(accurate)/nullif(sum(audited), 0), 0) as accuracy_percentage \
            FROM ({}) "table" \
            group by use_case_id, use_case_name, ml_model_id, ml_model_name, wafer_threshold \
            order by round(100*sum(accurate)/nullif(sum(audited), 0), 0) nulls first'.format(
            sql
        )
        # TODO: this should be separated out as a method, query formation and query execution
        if execute:
            with connection.cursor() as cursor:
                cursor.execute(output_sql, params)
                return CommonMetrics.dictfetchall(cursor)
        else:
            return output_sql, params

    @staticmethod
    def use_case_on_wafer_timeseries(input_queryset: QuerySet, execute=True):
        sql, params = input_queryset.query.sql_with_params()
        output_sql = '\
            SELECT use_case_id, effective_date,\
            count(wafer_id) as total, \
            count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold) as auto_classified, \
            count(wafer_id) - count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold) as manual, \
            round(100*(count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold))/nullif(count(wafer_id), 0), 0) as auto_classified_percentage \
            FROM ({}) "table" \
            group by use_case_id, effective_date \
            having count(wafer_id) > 0    \
            order by use_case_id, effective_date'.format(
            sql
        )
        # TODO: this should be separated out as a method, query formation and query execution
        if execute:
            with connection.cursor() as cursor:
                cursor.execute(output_sql, params)
                return CommonMetrics.dictfetchall(cursor)
        else:
            return output_sql, params

    @staticmethod
    def cohort_metrics(sql, params, condition, field):
        output_sql = '\
            SELECT {} as cohort, \
            count(*) as total, \
            array_agg({}) as {}, \
            round(100 * count(*) / nullif(sum(count(*)) over(), 0), 0) as percentage \
            FROM ({}) "table" \
            group by {} \
            '.format(
            condition, field, field + "s", sql, condition
        )
        with connection.cursor() as cursor:
            cursor.execute(output_sql, params)
            return CommonMetrics.dictfetchall(cursor)

    @staticmethod
    def wafer_distribution(input_queryset: QuerySet, execute=True):
        sql, params = input_queryset.query.sql_with_params()
        output_sql = '\
            SELECT \
            count(wafer_id) as total, \
            count(wafer_id) filter (where audited>0) as audited, \
            count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold) as auto_classified, \
            count(wafer_id) - count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold) as manual, \
            count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold and accuracy_percentage >= 90) as successful, \
            round(100*(count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold))/nullif(count(wafer_id), 0), 0) as auto_classified_percentage, \
            round(100*(count(wafer_id) filter (where auto_classified_percentage>=wafer_threshold and accuracy_percentage >= 90))/nullif(count(wafer_id), 0), 0) as successful_percentage, \
            sum(total) as total_files, \
            sum(auto_classified) as auto_classified_files, \
            sum(total) - sum(auto_classified) as manual_files, \
            sum(audited) as audited_files, \
            sum(accurate) as accurate_files, \
            sum(audited) - sum(accurate) as inaccurate_files, \
            round(100*sum(accurate)/nullif(sum(audited), 0), 0) as accuracy_percentage_files, \
            round(100*sum(accurate)/nullif(sum(audited), 0), 0) as accuracy_percentage \
            FROM ({}) "table" '.format(
            sql
        )
        # TODO: this should be separated out as a method, query formation and query execution
        if execute:
            result = []
            with connection.cursor() as cursor:
                cursor.execute(output_sql, params)
                result = CommonMetrics.dictfetchall(cursor)
            return result[0] if len(result) > 0 else result
        else:
            return output_sql, params
