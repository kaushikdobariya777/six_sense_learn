from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

from common.models import Base


class Organization(TenantMixin, Base):
    name = models.CharField(max_length=30)
    code = models.CharField(max_length=15)

    # Create schema automatically upon save.
    # https://github.com/django-tenants/django-tenants/blob/master/django_tenants/models.py#L26-L30
    auto_create_schema = True

    class Meta:
        db_table = "ss_organizations"

    def __str__(self):
        return self.name


class OrganizationDomain(DomainMixin):
    pass
