import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import status
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.models import SubOrganization
from apps.users.serializers import UserSerializer, SubOrganizationSerializer, GroupSerializer
from common.permissions import CustomObjectPermissions
from common.views import BaseViewSet

logger = logging.getLogger(__name__)


class SubOrganizationViewSet(BaseViewSet):
    serializer_class = SubOrganizationSerializer
    queryset = SubOrganization.objects.all().order_by("-id")

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        user_ids = self.request.data.get("users", [])
        instance.link_users(user_ids, self.request.user)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        user_ids = self.request.data.get("users", [])
        serializer.instance.link_users(user_ids, self.request.user)

    @action(detail=True, methods=["POST"])
    @permission_classes((IsAdminUser,))
    def assign_users(self, request, pk=None):
        try:
            instance = SubOrganization.objects.get(pk=pk)
            user_ids = request.data.get("users", [])
            logger.info("Linking %s users to %s branch API called by %s", user_ids, instance, self.request.user)
            instance.link_users(user_ids, self.request.user)
            return Response({"msg": "User assigned Successfully"}, status=status.HTTP_200_OK)
        except SubOrganization.DoesNotExist:
            return Response({"msg": "Sub organization does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as ex:
            logger.critical("Caught exception in {}".format(__file__), exc_info=True)
            return Response(
                {"msg": ex.args},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserViewSet(BaseViewSet):
    User = get_user_model()
    serializer_class = UserSerializer
    queryset = User.objects.filter().order_by("-id")

    def get_permissions(self):
        if self.action == "create":
            # ToDo: It shouldn't be AllowAny()
            return [AllowAny()]
        elif self.action == "list":
            return [IsAdminUser()]
        else:
            return [IsAuthenticated()]

    def perform_destroy(self, instance):
        user = self.User.objects.filter(id=instance.id).first()
        user.is_active = False
        user.save()
        instance.delete()

    @action(
        detail=False,
        methods=["GET"],
    )
    def me(
        self,
        request,
    ):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GroupViewSet(BaseViewSet):
    User = get_user_model()
    serializer_class = GroupSerializer
    queryset = Group.objects.all().order_by("-id")

    @action(detail=True, methods=["POST"], permission_classes=[CustomObjectPermissions])
    def assign_perm(self, request, pk=None):
        try:
            group = Group.objects.get(pk=pk)
            group.permissions.clear()
            permissions = request.data.get("permissions", [])
            for perm in permissions:
                permission = Permission.objects.get(codename=perm)
                group.permissions.add(permission)

            return Response({"msg": "Permission assigned successfully."}, status=status.HTTP_200_OK)
        except Exception as ex:
            logger.critical("Caught exception in {}".format(__file__), exc_info=True)
            return Response(
                {"msg": ex.args},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    @permission_classes((IsAdminUser,))
    def assign_users(self, request, pk=None):
        try:
            group = Group.objects.get(pk=pk)
            group.user_set.clear()
            users = request.data.get("users", [])
            for user in users:
                user = self.User.objects.get(id=user)
                group.user_set.add(user)

            return Response({"msg": "User assigned successfully."}, status=status.HTTP_200_OK)
        except Exception as ex:
            logger.critical("Caught exception in {}".format(__file__), exc_info=True)
            return Response(
                {"msg": ex.args},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
