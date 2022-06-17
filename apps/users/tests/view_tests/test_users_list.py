from django.contrib.auth import models
from rest_framework import status
from common.sixsense_test import CommonTest
from apps.user_auth.models import User


class UserViewSetTest(CommonTest):
    def test_list(self):
        # testing for all user listing
        response = self.admin_client.get("/api/v1/users/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEquals(User.objects.count(), response.data.get("count"))
