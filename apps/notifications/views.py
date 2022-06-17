from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from rest_framework import permissions, status, mixins
from rest_framework.decorators import permission_classes, api_view
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer

from rest_framework.pagination import CursorPagination


class CursorSetPagination(CursorPagination):
    page_size = 10
    page_size_query_param = "limit"
    ordering = "-created_ts"


class NotificationViewSet(mixins.UpdateModelMixin, mixins.ListModelMixin, GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = CursorSetPagination
    queryset = Notification.objects.all()


# TODO we can use NotificationViewSet get method to calculate the count
@permission_classes((permissions.IsAuthenticated,))
@api_view(["GET"])
def get_notification_count(request):
    queryset = Notification.objects.aggregate(
        total=Count("id"), is_unread=Count("id", filter=Q(is_read=False)), is_read=Count("id", filter=Q(is_read=True))
    )
    return Response(queryset, status=status.HTTP_200_OK)
