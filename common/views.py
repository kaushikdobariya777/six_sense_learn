import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from common.permissions import CustomObjectPermissions
from rest_framework.pagination import CursorPagination

logger = logging.getLogger(__name__)


class BaseViewSet(ModelViewSet):
    # General views should be written here
    permission_classes = [CustomObjectPermissions]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def enable_disable(self, request, pk=None):
        try:
            qs = self.get_queryset()
            resource = qs.model.__name__
            logger.info("PPP Enable/disable %s, called by '%s'", resource, request.user)
            qs.filter(pk=pk).update(is_active=request.data["is_active"])
            return Response({"msg": "%s updated" % resource}, status=status.HTTP_200_OK)
        except Exception as ex:
            logger.critical("Caught exception in {}".format(__file__), exc_info=True)
            return Response(
                {"msg": ex.args},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SixsenseCursorPagination(CursorPagination):
    page_size = 10
    page_size_query_param = "limit"
    ordering = "-created_ts"
