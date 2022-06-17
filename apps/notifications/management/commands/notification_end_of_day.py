from datetime import datetime

import pytz
from django.core.management import BaseCommand
from rest_framework.exceptions import ValidationError

from apps.notifications.services import NotificationService
from apps.subscriptions.models import Subscription


class Command(BaseCommand):
    """
    Whenever this command is executed, it will check the below conditions and trigger the notification,
    - Overall automation rate is less than expected
    - Automation is less than expected on one layer
    - Automation is less than expected on more than layer
    """

    help = "Generates notifications for overall and use case wise automation"

    def add_arguments(self, parser):
        parser.add_argument("--subscription_id", help="Subscription ID", required=True)
        parser.add_argument("--start_date", help="UTC Time Zone, 'yyyy-mm-dd hh-mm-ss'", required=True)
        parser.add_argument("--end_date", help="UTC Time Zone, 'yyyy-mm-dd hh-mm-ss'", required=True)

    @staticmethod
    def get_expected_automation(expected_automation):
        return expected_automation * 100

    def handle(self, start_date, end_date, subscription_id, *args, **options):
        print("Starting notification end of day command")
        print(start_date, end_date, subscription_id)
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").astimezone(pytz.utc)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").astimezone(pytz.utc)
        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            raise ValidationError(f"No subscription exist for the given subscription '{subscription_id}' ID.")
        print("Subscription found")
        expected_automation = self.get_expected_automation(subscription.expected_automation)
        notification_service = NotificationService()
        print("Calling execute_automation_less_than_expected of notification service")
        notification_service.execute_automation_less_than_expected(
            start_datetime=start_datetime, end_datetime=end_datetime, expected_automation=expected_automation
        )
        print("Calling execute_automation_less_than_expected_layer_level of notification service")
        notification_service.execute_automation_less_than_expected_layer_level(
            start_datetime=start_datetime, end_datetime=end_datetime, expected_automation=expected_automation
        )
