from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from apps.packs import views
from rest_framework.routers import SimpleRouter
from django.urls import include


router = SimpleRouter()
router.register("", views.PacksViewSet, basename="packs")

urlpatterns = router.urls

urlpatterns = format_suffix_patterns(urlpatterns)
