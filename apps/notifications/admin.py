from apps.notifications.models import NotificationScenario, Notification
from tenant_admin_site import admin_site
from django.contrib import admin


class NotificationScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "notification_type", "navigation_link", "is_active")


class NotificationAdmin(admin.ModelAdmin):
    list_display = ("scenario", "parameters", "is_read")


admin_site.register(NotificationScenario, NotificationScenarioAdmin)
admin_site.register(Notification, NotificationAdmin)
