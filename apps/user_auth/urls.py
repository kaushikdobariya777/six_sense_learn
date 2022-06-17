from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.user_auth.views import change_password, logout, CustomTokenObtainPairView

app_name = "user_auth"

urlpatterns = [
    path("login/", CustomTokenObtainPairView.as_view()),
    path("refresh_token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("logout/", logout),
    path("change_password/", change_password),
]
