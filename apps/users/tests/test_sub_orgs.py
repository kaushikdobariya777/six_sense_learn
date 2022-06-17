from django.urls import reverse
from rest_framework import status
from sixsense.tenant_test_case import SixsenseTenantTestCase


class TestSubOrganization(SixsenseTenantTestCase):
    def test_create_sub_org(self):
        url = reverse("users:sub_orgs-list")
        data = {"name": "makarba6 zone53", "code": "MKRB53", "address": "near prhladnagar"}
        # ToDo: Only admin user should be able to do this
        response = self.unauthorized_client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.authorized_client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.admin_client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_view_sub_org(self):
        url = reverse("users:sub_orgs-list")
        response = self.unauthorized_client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.authorized_client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.admin_client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # def test_no_view_permission(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = reverse('users:sub_orgs-list')
    #     response = self.client.get(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
    # def test_update_permission(self):
    #     url = reverse('users:sub_orgs-detail', kwargs={'pk': 1})
    #     data = {
    #         "name": "makarba6 zone53",
    #         "code": "MKRB53",
    #         "address": "near prhladnagar"
    #     }
    #     response = self.client.get(url, data=data, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    # def test__no_update_permission(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = reverse('users:sub_orgs-detail', kwargs={'pk': 1})
    #     data = {
    #         "name": "makarba6 zone53",
    #         "code": "MKRB53",
    #         "address": "near prhladnagar"
    #     }
    #     response = self.client.get(url, data=data, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
    # def test_delete_group(self):
    #     url = reverse('users:sub_orgs-detail', kwargs=({'pk': 1}))
    #     response = self.client.delete(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    #
    # def test_no_delete_permission(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = reverse('users:sub_orgs-detail', kwargs=({'pk': 2}))
    #     response = self.client.delete(url, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
    # def test_assign_user(self):
    #     url = '/api/v1/users/sub_orgs/1/assign_users/'
    #     response = self.client.post(url, data={'users': [2, 3]}, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    # def test_no_permission_assign_user(self):
    #     self.client.force_login(user=self.no_permission_user)
    #     url = '/api/v1/users/sub_orgs/1/assign_users/'
    #     response = self.client.post(url, data={'users': []}, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
