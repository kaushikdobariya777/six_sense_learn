from apps.subscriptions import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"", views.SubscriptionViewSet, basename="")

urlpatterns = router.urls
