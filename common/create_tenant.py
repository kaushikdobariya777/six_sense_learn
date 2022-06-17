from apps.organization.models import Organization, OrganizationDomain

tenant = Organization(schema_name="public", name="public", code="PUBLIC")
tenant.save()

domain = OrganizationDomain(domain="v2.sixsense.ai")
domain.tenant = tenant
domain.save()

tenant = Organization(schema_name="new", name="new", code="NEW")
tenant.save()

domain = OrganizationDomain(domain="127.0.0.1")
domain.tenant = tenant
domain.save()
