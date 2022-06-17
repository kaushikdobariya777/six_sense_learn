from rest_framework.response import Response
from apps.classif_ai.helpers import get_env
from django_filters import rest_framework as django_filters
from rest_framework import permissions, filters
from rest_framework.decorators import action

from apps.classif_ai.filters import UseCaseFilterSet
from apps.classif_ai.models import UseCase, Defect
from apps.classif_ai.serializers import UseCaseSerializer
from common.views import BaseViewSet


class UseCaseViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = UseCase.objects.all()
    serializer_class = UseCaseSerializer
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    ordering = ["-id"]
    # filterset_fields = ('subscription_id', )
    filter_class = UseCaseFilterSet

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    @action(methods=["GET"], detail=True)
    def defect_priority_order(self, request, pk):
        defect_ids = list(UseCase.objects.get(id=pk).defects.all().values_list("id", flat=True).order_by("created_ts"))
        ordered_defect_ids = get_env().list("ORDERED_DEFECT_IDS", cast=int, default=[1, 2, 4, 5, 3, 6])
        ordered_defect_ids.reverse()
        for defect_id in ordered_defect_ids:
            if defect_id in defect_ids:
                defect_ids.insert(0, defect_ids.pop(defect_ids.index(defect_id)))
        response = list(Defect.objects.filter(id__in=defect_ids).values("id", "name"))
        return Response(response)
