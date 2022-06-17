import logging
from datetime import timedelta

from django.db.models import F, FloatField
from django.db.models.functions import Cast
from rest_framework.exceptions import ValidationError

from apps.classif_ai.models import File, WaferMap
from apps.classif_ai.service.metrics_service import AutoClassificationMetrics, DistributionMetrics
from apps.notifications.models import NotificationScenario, Notification

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def annotate_queryset(queryset):
        return queryset.annotate(
            file_id=F("id"),
            gt_defect_id=F("gt_classifications__gt_classification_annotations__defect_id"),
            gt_defect_name=F("gt_classifications__gt_classification_annotations__defect__name"),
            model_defect_id=F("model_classifications__model_classification_annotations__defect__id"),
            model_defect_name=F("model_classifications__model_classification_annotations__defect__name"),
            confidence=F("model_classifications__model_classification_annotations__confidence"),
            confidence_threshold=F("model_classifications__ml_model__confidence_threshold"),
            ml_model_id=F("model_classifications__ml_model__id"),
            ml_model_name=F("model_classifications__ml_model__name"),
            use_case_id=F("file_set__use_case_id"),
            use_case_name=F("file_set__use_case__name"),
            wafer_id=F("file_set__wafer"),
            wafer_map_status=F("file_set__wafer__status"),
            wafer_map_created_time=F("file_set__wafer__created_ts"),
            organization_wafer_id=F("file_set__wafer__organization_wafer_id"),
            wafer_threshold=Cast(
                F("file_set__use_case__automation_conditions__threshold_percentage"),
                output_field=FloatField(),
            ),
            upload_session_id=F("file_set__upload_session_id"),
            upload_session_name=F("file_set__upload_session__name"),
        ).values(
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
            "wafer_map_status",
            "wafer_map_created_time",
            "wafer_threshold",
            "upload_session_id",
            "upload_session_name",
            "organization_wafer_id",
        )

    def filter_files(self, start_datetime, end_datetime):
        """
        Filter files based on start_datetime, end_datetime and ml_model status = deployed_in_prod
        """
        input_queryset = File.objects.filter(
            created_ts__gte=start_datetime,
            created_ts__lte=end_datetime,
            model_classifications__ml_model__status="deployed_in_prod",
        )
        queryset = self.annotate_queryset(input_queryset)
        return queryset

    def get_notification_scenario(self, scenario_name):
        """
        It will return the active notification scenario based on scenario_name
        """
        try:
            notification_scenario = NotificationScenario.objects.get(name=scenario_name, is_active=True)
        except NotificationScenario.DoesNotExist:
            raise ValidationError(f"No active notification scenario exist for '{scenario_name}' scenario")
        return notification_scenario

    def create_notification(self, notification_scenario, params):
        """
        Create the new notification if it doesn't exist in the system and run auto resolution
        """
        if not Notification.objects.filter(scenario=notification_scenario, parameters=params, is_read=False).exists():
            Notification.objects.create(scenario=notification_scenario, parameters=params)

    def execute_automation_less_than_expected(self, start_datetime, end_datetime, expected_automation):
        """
        It will check the overall automation is less than expected and create the notification.
        """
        queryset = self.filter_files(start_datetime, end_datetime)
        auto_classification_response = AutoClassificationMetrics.file_level(queryset)
        auto_classified_percentage = auto_classification_response.get("percentage")
        if auto_classified_percentage and auto_classified_percentage < expected_automation:
            below_expected = int(expected_automation - auto_classified_percentage)
            notification_scenario = self.get_notification_scenario(scenario_name="low_automation_overall")
            params = {"auto_classified_percentage": auto_classified_percentage, "below_expected": below_expected}
            self.create_notification(notification_scenario=notification_scenario, params=params)

    def execute_automation_less_than_expected_layer_level(self, start_datetime, end_datetime, expected_automation):
        """
        It will check the automation is less than expected on one usecase or multiple usecase and
        create the notification
        """
        queryset = self.filter_files(start_datetime, end_datetime)
        auto_classification_distributions = DistributionMetrics.file_distribution(
            queryset, group_by=["use_case_id", "use_case_name"]
        )
        use_case_names = []
        use_case_ids = []
        for distribution in auto_classification_distributions:
            use_case_id = distribution.get("use_case_id")
            use_case_name = distribution.get("use_case_name")
            auto_classified_percentage = distribution.get("auto_classified_percentage")
            if auto_classified_percentage and auto_classified_percentage < expected_automation:
                use_case_ids.append(use_case_id)
                use_case_names.append(use_case_name)
        if len(use_case_ids) > 1:
            use_case_count = len(use_case_ids)
            use_case_names = ", ".join(use_case_names)
            notification_scenario = self.get_notification_scenario(scenario_name="low_automation_multiple_use_cases")
            params = {"use_case_count": use_case_count, "use_cases": use_case_names, "use_case_ids": use_case_ids}
            self.create_notification(notification_scenario=notification_scenario, params=params)
        elif len(use_case_ids) == 1:
            below_expected = int(expected_automation - auto_classified_percentage)
            notification_scenario = self.get_notification_scenario(scenario_name="low_automation_single_use_case")
            params = {
                "use_case_name": use_case_name,
                "auto_classified_percentage": auto_classified_percentage,
                "use_case_ids": [use_case_id],
                "below_expected": below_expected,
            }
            self.create_notification(notification_scenario=notification_scenario, params=params)

    def execute_wafer_on_hold(self, current_datetime, more_than_hours=2):
        """
        It will find the wafers which are on hold more than X(default is 2 hours) hours and create the notification
        for the same
        """
        time_threshold = current_datetime - timedelta(hours=more_than_hours)
        notification_scenario = self.get_notification_scenario(scenario_name="wafer_on_hold_more_than_2_hours")
        filtered_wafers = WaferMap.objects.filter(
            status="manual_classification_pending", created_ts__lt=time_threshold
        )
        filtered_wafers_ids = list(filtered_wafers.values_list("id", flat=True))
        filtered_notifications = Notification.objects.filter(scenario=notification_scenario, is_read=False).annotate(
            wafer_id=F("parameters__wafer_id")
        )
        unread_wafers_ids = list(filtered_notifications.values_list("wafer_id", flat=True))
        new_wafers_ids = list(set(filtered_wafers_ids) - set(unread_wafers_ids))
        mark_as_read_wafers_ids = list(set(unread_wafers_ids) - set(filtered_wafers_ids))
        notifications = []
        for wafer_id in new_wafers_ids:
            organization_wafer_id = filtered_wafers.get(id=wafer_id).organization_wafer_id
            params = {"wafer_id": wafer_id, "organization_wafer_id": organization_wafer_id}
            notifications.append(Notification(scenario=notification_scenario, parameters=params))
        Notification.objects.bulk_create(notifications)
        filtered_notifications.filter(parameters__wafer_id__in=mark_as_read_wafers_ids).update(is_read=True)
