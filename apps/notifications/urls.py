from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.notifications import views

router = DefaultRouter()
router.register("", views.NotificationViewSet, "notifications")

urlpatterns = [
    path("get_count", views.get_notification_count, name="notification_count"),
    path("", include(router.urls)),
]
