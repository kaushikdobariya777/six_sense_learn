from rest_framework.routers import DefaultRouter

# from apps.users.views.auth_views import change_password, logout, CustomTokenObtainPairView
from apps.users.views import views

app_name = "users"

# urlpatterns = [
#     path('login/', CustomTokenObtainPairView.as_view()),
#     path('refresh_token/', TokenRefreshView.as_view(), name='token_refresh'),
#     path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
#     path('logout/', logout),
#     path('change_password/', change_password),
# ]

router = DefaultRouter()
router.register("groups", views.GroupViewSet, basename="groups")
router.register("sub_orgs", views.SubOrganizationViewSet, basename="sub_orgs")
router.register("", views.UserViewSet, basename="users")

# urlpatterns = urlpatterns + router.urls
urlpatterns = router.urls
