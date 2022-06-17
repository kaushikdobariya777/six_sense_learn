from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from common.services import S3Service
from apps.classif_ai.filters import WaferMapFilterSet
from apps.classif_ai.models import WaferMap
from apps.classif_ai.models import WaferMapTag
from apps.classif_ai.serializers import WaferMapReadSerializer, WaferMapSerializer
from common.views import BaseViewSet


class WaferMapViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    queryset = WaferMap.objects.all().defer("meta_data", "coordinate_meta_info", "defect_pattern_info")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_serializer_class(self):
        serializer = WaferMapSerializer
        if self.request.method == "GET" or self.request.method == "PATCH":
            if self.request.query_params.get("with_meta_info"):
                serializer = WaferMapSerializer
            else:
                serializer = WaferMapReadSerializer
        return serializer

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer_class()

        file_set_filter = WaferMapFilterSet(request.query_params, queryset=self.get_queryset(), request=request)
        queryset = file_set_filter.qs

        ordering = self.request.query_params.get("ordering")
        if ordering:
            ordering = ordering.split(",")
        else:
            ordering = ["updated_ts"]
        queryset = queryset.order_by(*ordering)
        limit = self.request.query_params.get("limit")
        if limit:
            queryset = queryset[: int(limit)]
        serialized = serializer(queryset, many=True)
        return Response(serialized.data)

    # @staticmethod
    # def filter_wafers(query_params):
    #     # ToDo: We shouldn't be using FileSetFilterSet for filtering the wafers. It should have it's own filterset
    #     file_set_filter = FileSetFilterSet(query_params, queryset=FileSet.objects.all())
    #     query_set = file_set_filter.qs
    #     wafer_ids = list(query_set.values_list("wafer_id", flat=True).distinct())
    #     wafers = WaferMap.objects.filter(pk__in=wafer_ids)
    #     return wafers

    def add_tags(self, qs, tag_ids):
        """
        Add the tags for the specified waferMap.
        """
        # ToDo: This API could be very slow if the qs count is very high
        #   At the time of writing, django didn't support insert select.
        #   Sample SQL:
        #       INSERT INTO WaferMapTag(wafer_id, tag_id)
        #       SELECT wafermaps.id, tags.id
        #       FROM wafermaps  full outer join tags
        #       WHERE  wafermaps.id in (1,2) and tags.id in (4,5)
        wafer_map_tags = []
        for wafer in qs.values("id"):
            for tag_id in tag_ids:
                wafer_map_tags.append(WaferMapTag(wafer_id=wafer["id"], tag_id=tag_id))
        WaferMapTag.objects.bulk_create(wafer_map_tags)

    def remove_tags(self, qs, tag_ids=None, remove_all=False):
        """
        Remove the tags from the specified waferMap.
        """
        if remove_all:
            WaferMapTag.objects.filter(wafer__in=qs).delete()
        elif tag_ids:
            WaferMapTag.objects.filter(wafer__in=qs, tag_id__in=tag_ids).delete()

    filter_params = [
        OpenApiParameter(
            name="tag_ids",
            type={"type": "list"},
            location=OpenApiParameter.QUERY,
            style="form",
        )
    ]

    @extend_schema(parameters=filter_params)
    @action(detail=False, methods=["PUT", "DELETE"], url_name="tags", url_path="tags")
    def tags(self, request):
        """
        This endpoint is used to add/remove the tags on wafers.

        In PUT: Add the tags
        In DELETE: Remove the tags

        query-params: It will support the FileSetFilters.

        """
        queryset = self.filter_queryset(self.get_queryset())
        request_method = request.method
        # filter_params = request.query_params
        tag_ids = request.data.get("tag_ids", None)
        if request_method == "PUT":
            if not tag_ids:
                return Response({"error": "tag_ids is required field"}, status=status.HTTP_400_BAD_REQUEST)
            self.add_tags(qs=queryset, tag_ids=tag_ids)
            return Response({"success": "tags added successfully."}, status=status.HTTP_200_OK)
        elif request_method == "DELETE":
            remove_all_tags = False
            if tag_ids is None and request.data.get("remove_all_tags", False) is True:
                remove_all_tags = True
            self.remove_tags(qs=queryset, tag_ids=tag_ids, remove_all=remove_all_tags)
            return Response({"success": "tags removed successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Method '%s' not allowed." % request_method}, status=status.HTTP_400_BAD_REQUEST)
