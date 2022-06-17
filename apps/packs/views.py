from apps.packs.models import Pack
from apps.packs.serializers import PackSerializer
from django.http import Http404, JsonResponse
from rest_framework.response import Response
from rest_framework import status, filters
from rest_framework import permissions
from django.db.models import Q
from rest_framework import viewsets


class PacksViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for listing or retrieving packs.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PackSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ["id"]

    def get_queryset(self):
        sub_org_id = self.request.GET.get("sub_organization_id")
        return Pack.objects.filter(sub_organizations=sub_org_id, is_active=True)


# class SubscriptionViewSet(viewsets.ModelViewSet):

#     permission_classes = [permissions.AllowAny]
#     serializer_class = PackSerializer
#     def get_queryset(self):
#         org_id = self.request.GET.get('org_id')
#         return Pack.objects.filter(subscription__sub_organization_id = org_id)
