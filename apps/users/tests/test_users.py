from django.urls import reverse
from rest_framework import status
from sixsense.tenant_test_case import SixsenseTenantTestCase


class TestProfile(SixsenseTenantTestCase):
    pass
    # def test_create_profile(self):
    # url = reverse('users:users-list')
    # data = {
    # "first_name": "cool",
    # "last_name": "testing",
    # "username": "test2",
    # "email": "cool2@admin.com",
    # "password": "test2@12334",
    # "phone": "+918062915623"
    # }
    # response = self.unauthorized_client.post(url, data=data, format='json')
    # self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # def test_view_profile(self):
    #     url = reverse('users:users-list')
    #     response = self.authorized_client.get(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)

    # def test_no_view_permission(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = reverse('users:users-list')
    #     response = self.client.get(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # def test_update_permission(self):
    #     url = reverse('users:users-detail', kwargs={'pk': 1})
    #     data = {
    #         "first_name": "Test",
    #         "last_name": "User",
    #         "email": "test@test.ai",
    #         "password": "876653@123hg",
    #         "phone": "84757583"
    #     }
    #     response = self.client.get(url, data=data, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)

    # def test_no_update_permission(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = reverse('users:users-detail', kwargs={'pk': 1})
    #     data = {
    #         "first_name": "Test",
    #         "last_name": "User",
    #         "email": "test@test.ai",
    #         "password": "876653@123hg",
    #         "phone": "84757583"
    #     }
    #     response = self.client.get(url, data=data, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # def test_delete_profile(self):
    #     url = reverse('users:users-detail', kwargs=({'pk': 2}))
    #     response = self.client.delete(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # def test_no_delete_permission(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = reverse('users:users-detail', kwargs=({'pk': 2}))
    #     response = self.client.delete(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
