import os

from django.core.exceptions import SuspiciousOperation
from django.db import connection
from django.utils._os import safe_join
from storages.backends.s3boto3 import S3Boto3Storage
from django_tenants.files.storage import TenantFileSystemStorage

from sixsense import settings


class TenantFileSystemS3Storage(S3Boto3Storage):
    # ToDo: Need to test if this class properly behaves with S3 or not
    pass
    # @property  # not cached like in parent of S3Boto3Storage class
    # def location(self):
    #     return os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name)
    # _location = utils.parse_tenant_config_path(
    #     settings.AWS_PRIVATE_MEDIA_LOCATION) # here you can just put '%s'
    # return _location


class TenantOnPremFileSystemStorage(TenantFileSystemStorage):
    def path(self, name):
        """
        Look for files in subdirectory of MEDIA_ROOT using the tenant's
        domain_url value as the specifier.
        """
        if name is None:
            name = ""
        try:
            location = safe_join(self.location, connection.tenant.schema_name)
        except AttributeError:
            location = self.location
        try:
            path = safe_join(location, name)
        except ValueError:
            raise SuspiciousOperation("Attempted access to '%s' denied." % name)
        return os.path.normpath(path)
