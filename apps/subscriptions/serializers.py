from rest_framework import serializers

from apps.subscriptions.models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):

    user_count = serializers.SerializerMethodField(read_only=True)
    fileset_count = serializers.SerializerMethodField(read_only=True)
    ml_model_count = serializers.SerializerMethodField(read_only=True)
    upload_session_count = serializers.SerializerMethodField(read_only=True)

    def get_user_count(self, obj):
        return obj.sub_organization.users.all().count()

    def get_fileset_count(self, obj):
        return obj.file_sets.all().count()

    def get_ml_model_count(self, obj):
        return obj.ml_models.exclude(status="deleted").count()

    def get_upload_session_count(self, obj):
        return obj.upload_sessions.all().count()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "created_ts",
            "pack",
            "sub_organization",
            "expires_at",
            "starts_at",
            "status",
            "file_set_meta_info",
            "user_count",
            "fileset_count",
            "ml_model_count",
            "upload_session_count",
            "overkill_defect_config",
            "expected_automation",
        ]
