from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"

    # TODO Remove nested notification field and add all fields directly to the data
    def to_representation(self, instance):
        data = super(NotificationSerializer, self).to_representation(instance)
        data["notification"] = {
            "title": str(instance.scenario.title).format(**instance.parameters),
            "description": str(instance.scenario.description).format(**instance.parameters),
            "notification_type": instance.scenario.notification_type,
            "navigation_link": str(instance.scenario.navigation_link).format(**instance.parameters),
            "priority": instance.scenario.priority,
        }
        return data
