import pytz
from django.core.management.base import BaseCommand
from datetime import datetime

from apps.notifications.services import NotificationService


class Command(BaseCommand):
    """
    Whenever this command is executed, it checks all wafers which are on hold for more than 2 hours
    and notifies the users. If for one wafer, it is already notified in any of the previous notifications,
    that wafer will not be notified again.
    """

    help = "Generates notifications for wafers on hold for more than a threshold time (default=2 hours)"

    def __init__(self):
        super().__init__()
        self.current_datetime = datetime.utcnow().astimezone(pytz.utc)
        self.more_than_hours = 2

    def handle(self, *args, **options):
        print("Starting notifications every x hours command")
        notification_service = NotificationService()
        print("Calling execute_wafer_on_hold of NotificationService")
        notification_service.execute_wafer_on_hold(
            current_datetime=self.current_datetime, more_than_hours=self.more_than_hours
        )
