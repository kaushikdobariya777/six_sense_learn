from rest_framework import serializers
from apps.packs.models import Pack, OrgPack


class PackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pack
        fields = [
            "id",
            "created_ts",
            "name",
            "type",
            "is_demo",
            "is_active",
            "image",
            "category",
            "image_type",
            "process",
            "manufacturing",
        ]
