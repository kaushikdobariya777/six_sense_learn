import logging

from django.core.exceptions import ValidationError
from django_filters import rest_framework as django_filters
from drf_spectacular.utils import extend_schema, OpenApiParameter

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.classif_ai.filters import UserClassificationFilterSet, UserDetectionFilterSet
from apps.classif_ai.models import UserClassification, UserDetection
from apps.classif_ai.serializers import UserClassificationSerializer, UserDetectionSerializer
from apps.classif_ai.services import UserAnnotationBulkActionService
from apps.classif_ai.helpers import get_filters_from_request_object

logger = logging.getLogger(__name__)


class UserClassificationViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = UserClassification.objects.all()
    serializer_class = UserClassificationSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = UserClassificationFilterSet

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"defects": self.request.data.get("defects", None), "user": self.request.user})
        return context

    def retrieve(self, request, *args, **kwargs):
        response = {"message": "Create function is not offered in this path."}
        return Response(response, status=status.HTTP_403_FORBIDDEN)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="defects",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
            OpenApiParameter(
                name="file_ids",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
        ]
    )
    @action(detail=False, methods=["post"], url_name="bulk_create", url_path="bulk_create")
    def bulk_create(self, request):
        """
        Create bulk classification for one or more files.
        """
        request_data = request.data
        request_data["user"] = request.user.id
        bulk_action_service = UserAnnotationBulkActionService(request_data)
        # ToDo: bulk create method should accept more filters other than file ids alone
        try:
            bulk_action_service.classification_bulk_create(
                file_ids=request.data.get("file_ids", None),
                defect_ids=request.data.get("defects", None),
                user_id=request.user.id,
                is_no_defect=request.data.get("is_no_defect"),
                replace_existing_labels=request.data.get("replace_existing_labels", False),
            )
        except ValidationError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)
        # bulk_action_service.classification_bulk_create(filters=get_filters_from_request_object(request))
        return Response(status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="original_defect",
                type={"type": "str"},
                location=OpenApiParameter.QUERY,
                required=True,
                style="form",
            ),
            OpenApiParameter(
                name="new_defect",
                type={"type": "str"},
                location=OpenApiParameter.QUERY,
                required=True,
                style="form",
            ),
            OpenApiParameter(
                name="file_ids",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=True,
                style="form",
            ),
        ]
    )
    @action(detail=False, methods=["post"], url_name="bulk_replace", url_path="bulk_replace")
    def bulk_replace(self, request):
        """
        Replace classification for one or more files.
        """
        original_defect = request.data.get("original_defect", None)
        new_defect = request.data.get("new_defect", None)
        if not (original_defect or new_defect):
            return Response(
                "Please send the original_defect and new_defect parameters.", status=status.HTTP_400_BAD_REQUEST
            )
        request_data = request.data
        request_data["user"] = request.user.id
        bulk_action_service = UserAnnotationBulkActionService(request_data)
        bulk_action_service.classification_bulk_replace(
            file_ids=request.data.get("file_ids", None),
            original_defect=request.data.get("original_defect"),
            new_defect=request.data.get("new_defect"),
            user_id=request.user.id,
        )
        # bulk_action_service.classification_bulk_replace(filters=get_filters_from_request_object(request))
        return Response(status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="remove_all",
                type={"type": "boolean"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
            OpenApiParameter(
                name="defects",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
            OpenApiParameter(
                name="file_ids",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
        ]
    )
    @action(detail=False, methods=["post"], url_name="bulk_remove", url_path="bulk_remove")
    def bulk_remove(self, request):
        """
        Delete classification for one or more files.
        """
        defect_ids = request.data.get("defects", None)
        remove_all = request.data.get("remove_all", False)
        if defect_ids and remove_all:
            return Response(
                "You can't send defect_ids along with remove_all as True.", status=status.HTTP_400_BAD_REQUEST
            )
        request_data = request.data
        request_data["user"] = request.user.id
        bulk_action_service = UserAnnotationBulkActionService(request_data)
        try:
            bulk_action_service.classification_bulk_remove(
                file_ids=request.data.get("file_ids", None),
                defect_ids=request.data.get("defects", None),
                remove_all=request.data.get("remove_all", False),
                user_id=request.user.id,
            )
        except ValidationError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)
        # bulk_action_service.classification_bulk_remove(filters=get_filters_from_request_object(request))
        return Response(status=status.HTTP_200_OK)


class UserDetectionViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = UserDetection.objects.all()
    serializer_class = UserDetectionSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filter_class = UserDetectionFilterSet

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(
            {"detection_regions": self.request.data.get("detection_regions", None), "user": self.request.user}
        )
        return context

    def retrieve(self, request, *args, **kwargs):
        response = {"message": "Create function is not offered in this path."}
        return Response(response, status=status.HTTP_403_FORBIDDEN)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="remove_all",
                type={"type": "boolean"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
            OpenApiParameter(
                name="defects",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
            OpenApiParameter(
                name="files",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=False,
                style="form",
            ),
        ]
    )
    @action(detail=False, methods=["post"], url_name="bulk_remove", url_path="bulk_remove")
    def bulk_remove(self, request):
        """
        Delete detection for one or more files.
        """
        defect_ids = request.data.get("defects", None)
        remove_all = request.data.get("remove_all", False)
        if defect_ids and remove_all:
            return Response(
                "You can't send defect_ids along with remove_all as True.", status=status.HTTP_400_BAD_REQUEST
            )
        request_data = request.data
        request_data["user"] = request.user.id
        bulk_action_service = UserAnnotationBulkActionService(request_data)
        # bulk_action_service.detection_bulk_remove(filters=get_filters_from_request_object(request))
        try:
            bulk_action_service.detection_bulk_remove(
                file_ids=request.data.get("file_ids", None),
                defect_ids=request.data.get("defects", None),
                remove_all=request.data.get("remove_all", False),
                user_id=request.user.id,
            )
        except ValidationError as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="original_defect",
                type={"type": "str"},
                location=OpenApiParameter.QUERY,
                required=True,
                style="form",
            ),
            OpenApiParameter(
                name="new_defect",
                type={"type": "str"},
                location=OpenApiParameter.QUERY,
                required=True,
                style="form",
            ),
            OpenApiParameter(
                name="files",
                type={"type": "list"},
                location=OpenApiParameter.QUERY,
                required=True,
                style="form",
            ),
        ]
    )
    @action(detail=False, methods=["post"], url_name="bulk_replace", url_path="bulk_replace")
    def bulk_replace(self, request):
        """
        Replace detection for one or more files.
        """
        original_defect = request.data.get("original_defect")
        new_defect = request.data.get("new_defect")
        if not (original_defect or new_defect):
            return Response(
                "Please send the original_defect and new_defect parameters.", status=status.HTTP_400_BAD_REQUEST
            )
        request_data = request.data
        request_data["user"] = request.user.id
        bulk_action_service = UserAnnotationBulkActionService(request_data)
        bulk_action_service.detection_bulk_replace(
            file_ids=request.data.get("file_ids", None),
            original_defect=request.data.get("original_defect"),
            new_defect=request.data.get("new_defect"),
            user_id=request.user.id,
        )
        return Response(status=status.HTTP_200_OK)
