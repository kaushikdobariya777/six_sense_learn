from rest_framework.test import APIClient
from django_tenants.test.client import TenantClient


class APITenantClient(TenantClient, APIClient):
    pass
