"""sixsense URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


from tenant_admin_site import admin_site

urlpatterns = [
    path("api/admin/", admin_site.urls),
    path("api/v1/users/", include("apps.user_auth.urls"), name="users"),
    path("api/v1/users/", include("apps.users.urls"), name="users"),
    path("api/v1/packs/", include("apps.packs.urls"), name="packs"),
    path("api/v1/subscriptions/", include("apps.subscriptions.urls"), name="subscriptions"),
    path("api/v1/classif-ai/", include("apps.classif_ai.urls"), name="classif-ai"),
    path("api/v1/notifications/", include("apps.notifications.urls"), name="notifications"),
    path("api/v2/classif-ai/", include("apps.classif_ai.v2_urls"), name="classif-ai-v2"),
]

urlpatterns += [
    # YOUR PATTERNS
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI:
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# https://docs.djangoproject.com/en/3.2/howto/static-files/#serving-files-uploaded-by-a-user-during-development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
