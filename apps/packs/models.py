import os

from django.core.files.storage import get_storage_class
from django.db import models, connection
from apps.organization.models import Base, Organization
from apps.users.models import SubOrganization
from sixsense import settings

file_storage = get_storage_class()


class OrgPack(Base):
    pack = models.ForeignKey("Pack", on_delete=models.CASCADE)
    sub_organization = models.ForeignKey(SubOrganization, on_delete=models.PROTECT)


class Pack(Base):
    def get_upload_path(self, filename):
        return os.path.join(settings.MEDIA_ROOT, connection.tenant.schema_name, filename)

    CATEGORY_CHOICES = (("FRONTEND", "Frontend"), ("BACKEND", "Backend"))

    name = models.CharField(max_length=100, blank=True, default="")
    type = models.CharField(max_length=100, blank=True, default="Public")
    is_demo = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sub_organizations = models.ManyToManyField(through=OrgPack, to=SubOrganization, related_name="packs")
    image = models.ImageField(
        storage=file_storage(), null=True, blank=True, max_length=1024, upload_to=get_upload_path
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="BACKEND", blank=True)
    image_type = models.CharField(max_length=40, blank=True)
    process = models.CharField(max_length=40, blank=True)
    manufacturing = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return self.name + "-" + self.type


# class Subscription(Base):
#     pack = models.ForeignKey('Pack' , on_delete=models.PROTECT)
#     sub_organization_id = models.ForeignKey(SubOrganization , on_delete = models.PROTECT)
#     expires_at = models.DateTimeField()
#     starts_at = models.DateTimeField(null = True)
#     status= models.CharField(default='ACTIVE' , max_length = 100)
