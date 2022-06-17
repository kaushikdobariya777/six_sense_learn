from rest_framework.decorators import action, api_view, permission_classes
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from apps.classif_ai.service import detection_service


class DetectionViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def smoke(self, request):
        return Response("smoked!", status=status.HTTP_200_OK)
