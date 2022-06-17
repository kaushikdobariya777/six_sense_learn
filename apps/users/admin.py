from apps.users.models import SubOrganization

# admin.site.register(Profile)
from tenant_admin_site import admin_site

admin_site.register(SubOrganization)
