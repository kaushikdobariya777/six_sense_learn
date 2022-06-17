from django.core.exceptions import ValidationError
from django_filters import rest_framework as django_filters
from rest_framework import permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q

from apps.classif_ai.filters import MlModelFilterSet
from apps.classif_ai.models import MlModel, MlModelDefect
from apps.classif_ai.serializers import MlModelDetailSerializer, MlModelCreateSerializer, MlModelListSerializer
from common.views import BaseViewSet


class MlModelViewSet(BaseViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = MlModel.objects.exclude(status="deleted")
    filter_backends = [
        django_filters.DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    ordering = ["code", "-id"]
    ordering_fields = ["name", "version"]
    # filterset_fields = ('name', 'code', 'version', 'status', 'is_stable', 'subscription_id', 'use_case_id')
    filter_class = MlModelFilterSet

    def get_serializer_class(self):
        if self.action == "retrieve":
            # return MlModelDetailSerializer
            # ToDo: Sai. Add more things in Detail serializer and use that instead of using list serializer
            return MlModelListSerializer
        elif self.action == "create":
            return MlModelCreateSerializer
        return MlModelListSerializer

    def perform_destroy(self, instance):
        instance.status = "deleted"
        instance.save()

    @action(
        methods=[
            "PATCH",
        ],
        detail=True,
    )
    def deploy(self, request, pk):
        try:
            ml_model = MlModel.objects.get(id=pk)
            ml_model.deploy()
            return Response(f"Successfully deployed ml model {pk} in production.", status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {"msg": f"Unable to deploy deployed ml model {pk} in production.", "exception": e.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(methods=["POST", "DELETE"], detail=True, url_name="defects", url_path="defects")
    def bulk_add_defects(self, request, pk):
        defect_ids = request.data.get("defects", None)
        if not defect_ids:
            return Response("Please send the defect ids to add", status=status.HTTP_400_BAD_REQUEST)
        if request.method == "POST":
            ml_model_defects = [MlModelDefect(ml_model_id=pk, defect_id=int(defect)) for defect in defect_ids]
            MlModelDefect.objects.bulk_create(ml_model_defects, ignore_conflicts=True)
            return Response(f"Added {len(defect_ids)} defects successfully.")
        elif request.method == "DELETE":
            MlModelDefect.objects.filter(ml_model_id=pk, defect_id__in=defect_ids).delete()
            return Response(f"Deleted {len(defect_ids)} defects successfully.")
        else:
            return Response(f"Method '{self.action}' not allowed.")

    @action(
        methods=[
            "PATCH",
        ],
        detail=True,
    )
    def undeploy(self, request, pk):
        try:
            ml_model = MlModel.objects.get(id=pk)
            ml_model.undeploy()
            return Response(f"Successfully undeployed ml model {pk} in production.", status=status.HTTP_200_OK)
        except MlModel.DoesNotExist as e:
            return Response(
                {"msg": f"ml model {pk} does not exist.", "exception": e.message}, status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationError as e:
            return Response(
                {"msg": f"Unable to deploy deployed ml model {pk} in production.", "exception": e.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
