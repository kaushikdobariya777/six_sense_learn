from django.db import models
from common.models import Base


class NotificationScenario(Base):
    NOTIFICATION_TYPE_CHOICES = (("EMAIL", "EMAIL"), ("WEB", "WEB"))
    NOTIFICATION_PRIORITY_CHOICES = (("High", "High"), ("Medium", "Medium"), ("Low", "Low"))
    name = models.CharField(max_length=200, null=True, blank=True)
    title = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, default=None)
    navigation_link = models.CharField(max_length=200, null=True, blank=True)
    priority = models.CharField(max_length=50, choices=NOTIFICATION_PRIORITY_CHOICES, default="Low")
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications_notification_scenario"

    def __str__(self):
        return "%s: %s" % (self.name, self.title)


class Notification(Base):
    scenario = models.ForeignKey(NotificationScenario, on_delete=models.PROTECT, related_name="notification_scenario")
    parameters = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications_notification"
