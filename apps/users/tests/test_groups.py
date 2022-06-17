from django.urls import reverse
from rest_framework import status
from common.sixsense_test import CommonTest


# class TestGroup(CommonTest):
#
#     def test_create_group(self):
#         url = reverse('users:groups-list')
#         data = {
#                 "name": "manager",
#                 "permissions": []
#             }
#         response = self.client.post(url, data=data, format='json')
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#
#     def test_view_group(self):
#         url = reverse('users:groups-list')
#         response = self.client.get(url, format='json')
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#     def test_no_view_permission(self):
#         self.client.force_login(user=self.no_permission_user)
#         url = reverse('users:groups-list')
#         response = self.client.get(url, format='json')
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
#
#     def test_update_permission(self):
#         url = reverse('users:groups-detail', kwargs={'pk': 1})
#         data = {
#                 "name": "manager",
#                 "permissions": ['add_profile']
#             }
#         response = self.client.get(url, data=data, format='json')
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#     def test__no_update_permission(self):
#         self.client.force_login(user=self.no_permission_user)
#         url = reverse('users:groups-detail', kwargs={'pk': 1})
#         data = {
#                 "name": "manager",
#                 "users": [2, 3],
#                 "permissions": ['add_profile']
#             }
#         response = self.client.get(url, data=data, format='json')
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
#
#     def test_delete_group(self):
#         url = reverse('users:groups-detail', kwargs=({'pk': 1}))
#         response = self.client.delete(url, format='json')
#         self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
#
#     def test_no_delete_permission(self):
#         self.client.force_login(user=self.no_permission_user)
#         url = reverse('users:groups-detail', kwargs=({'pk': 2}))
#         response = self.client.delete(url, format='json')
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
#
#     def test_assign_user(self):
#         url = '/api/v1/users/groups/1/assign_users/'
#         response = self.client.post(url, data={'users': [2]}, format='json')
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#     def test_no_permission_assign_user(self):
#         self.client.force_login(user=self.no_permission_user)
#         url = '/api/v1/users/groups/1/assign_users/'
#         response = self.client.post(url, data={'users': []}, format='json')
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
#
#     def test_assign_perms(self):
#         url = '/api/v1/users/groups/1/assign_perm/'
#         response = self.client.post(url, data={'permissions': []}, format='json')
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#     def test_no_permission_assign_perm(self):
#         self.client.force_login(user=self.no_permission_user)
#         url = '/api/v1/users/groups/1/assign_users/'
#         response = self.client.post(url, data={'users': []}, format='json')
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
