from rest_framework import permissions
from rest_framework import viewsets

from apps.subscriptions.models import Subscription
from apps.subscriptions.serializers import SubscriptionSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        sub_org_id = self.request.GET.get("sub_organization_id")
        if sub_org_id:
            return Subscription.objects.filter(sub_organization_id=sub_org_id, status="ACTIVE")
        return Subscription.objects.all()
