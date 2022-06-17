from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.test.cases import TenantTestCase

from common.tenant_api_client import APITenantClient

TEST_USER_EMAIL = "xxx@xxx.com"
TEST_USER_PASSWORD = "1234567890"
TEST_USER_FIRST_NAME = "Test"
TEST_USER_LAST_NAME = "User"

ADMIN_USER_EMAIL = "admin@xxx.com"
ADMIN_USER_PASSWORD = "admin123"
ADMIN_USER_FIRST_NAME = "Admin"
ADMIN_USER_LAST_NAME = "User"


class SixsenseTenantTestCase(APITestCase, TenantTestCase):
    @classmethod
    def setUpTestData(cls):
        # TODO: Create multiple types of users, suborganization, suborganizationusermapping using fixtures
        super(SixsenseTenantTestCase, cls).setUpTestData()
        get_user_model().objects.create_user(
            email=TEST_USER_EMAIL,
            password=TEST_USER_PASSWORD,
            first_name=TEST_USER_FIRST_NAME,
            last_name=TEST_USER_LAST_NAME,
            is_active=True,
        )

        get_user_model().objects.create_user(
            email=ADMIN_USER_EMAIL,
            password=ADMIN_USER_PASSWORD,
            first_name=ADMIN_USER_FIRST_NAME,
            last_name=ADMIN_USER_LAST_NAME,
            is_active=True,
            is_superuser=True,
            is_staff=True,
        )

    def setUp(self) -> None:
        super(SixsenseTenantTestCase, self).setUp()
        self.user = get_user_model().objects.filter(email=TEST_USER_EMAIL).first()
        self.admin_user = get_user_model().objects.filter(email=ADMIN_USER_EMAIL).first()
        user_token = RefreshToken.for_user(self.user)
        user_access_key = str(user_token.access_token)
        admin_token = RefreshToken.for_user(self.admin_user)
        admin_access_key = str(admin_token.access_token)
        self.unauthorized_client = APITenantClient(self.tenant)
        self.authorized_client = APITenantClient(self.tenant, HTTP_AUTHORIZATION="Bearer " + user_access_key)
        self.admin_client = APITenantClient(self.tenant, HTTP_AUTHORIZATION="Bearer " + admin_access_key)

    @classmethod
    def setUpClass(cls):
        # This below line will call setUpClass in the TenantTestCase as APITestCase doesn't have setUpClass
        super().setUpClass()
        # This below line will call setUpClass in the TestCase
        super(TenantTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TenantTestCase, cls).tearDownClass()
        super().tearDownClass()
