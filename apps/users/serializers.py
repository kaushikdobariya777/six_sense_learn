import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import ProgrammingError
from rest_framework import exceptions, serializers

from apps.users.models import SubOrganization, OrganizationUser

logger = logging.getLogger(__name__)


class PermissionSerializer(serializers.ModelSerializer):
    model = serializers.ReadOnlyField(source="content_type.model")

    class Meta:
        model = Permission
        fields = ("codename", "model", "name")


class GroupSerializer(serializers.ModelSerializer):
    users = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ("id", "name", "permissions", "users")

    def create(self, validated_data):
        users = self.initial_data.get("users", [])
        permissions = self.initial_data.get("permissions", [])
        group = Group.objects.create(**validated_data)
        for perm in permissions:
            permission = Permission.objects.get(codename=perm)
            group.permissions.add(permission)

        for user in users:
            user = get_user_model().objects.filter(id=user).first()
            if user:
                group.user_set.add(user)
        return group

    def update(self, instance, validated_data):
        users = self.initial_data.get("users", [])
        permissions = self.initial_data.get("permissions", [])
        instance.name = validated_data["name"]
        instance.save()
        instance.permissions.clear()
        for perm in permissions:
            permission = Permission.objects.get(codename=perm)
            instance.permissions.add(permission)

        if users:
            instance.user_set.clear()
        for user in users:
            user = get_user_model().objects.filter(id=user).first()
            if user:
                instance.user_set.add(user)
        return instance

    def get_users(self, instance):
        try:
            return UserSerializer(instance=instance.user_set.all(), many=True, remove_fields=[]).data
        except AttributeError as ex:
            return []

    def get_permissions(self, instance):
        try:
            perms = PermissionSerializer(instance=instance.permissions.all(), many=True).data
            return [perm["codename"] for perm in perms]
        except AttributeError as ex:
            return []


class SubOrganizationSerializer(serializers.ModelSerializer):
    users = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SubOrganization
        fields = ("id", "name", "code", "address", "users")

    def get_users(self, instance):
        users = list(instance.users.all().values("first_name", "last_name", "id", "email"))
        return users


class UserSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    password = serializers.CharField(write_only=True)
    sub_organizations = serializers.SerializerMethodField(read_only=True)

    def __init__(self, *args, **kwargs):
        remove_fields = kwargs.pop("remove_fields", None)
        super(UserSerializer, self).__init__(*args, **kwargs)

        if remove_fields:
            for field_name in remove_fields:
                self.fields.pop(field_name)

        if "request" in self.context and self.context["request"].method == "PUT":
            self.fields.pop("password")

    def get_sub_organizations(self, instance):
        # On create there will be no user in instance so passing []
        try:
            return SubOrganizationSerializer(instance.sub_organizations.all(), many=True).data
        except AttributeError as ex:
            return []
        except ProgrammingError as ex:
            return []

    def create(self, validated_data):
        user = get_user_model()(**validated_data)
        user.set_password(validated_data["password"])
        user.is_active = False
        user.save()
        return user

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "password",
            "phone",
            "display_name",
            "created_by",
            "sub_organizations",
            "is_staff",
            "is_active",
            "is_superuser",
        )
        read_only_fields = ("is_active", "is_superuser")
