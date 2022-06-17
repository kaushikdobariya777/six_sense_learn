from django.db import connection

from apps.classif_ai.filters import TaskResultFilterSet
from apps.classif_ai.tasks import copy_images_to_folder
from common.views import BaseViewSet, SixsenseCursorPagination
from django_celery_results.models import TaskResult
from apps.classif_ai.serializers import TaskResultSerializer
from django_filters import rest_framework as django_filters
from rest_framework import filters
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import action
import ast


class TaskResultCursorPagination(SixsenseCursorPagination):
    ordering = "-date_created"


class TaskResultViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = TaskResult.objects.all()
    serializer_class = TaskResultSerializer
    pagination_class = TaskResultCursorPagination
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    lookup_field = "task_id"
    filter_class = TaskResultFilterSet
    ordering = "-date_created"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    @action(detail=False, methods=["PUT"], url_path="(?P<task_id>[0-9A-Fa-f-]+)/retry")
    def retry(self, request, task_id):
        task = TaskResult.objects.get(task_id=task_id)
        if task.status == "FAILURE":
            args = ast.literal_eval(str(task.task_args))
            copy_images_to_folder.apply_async(args, task_id=task_id, kwargs={"schema": connection.schema_name})
            return Response("task {} is being retried".format(task_id))
        return Response("Only failure task can be retry")
