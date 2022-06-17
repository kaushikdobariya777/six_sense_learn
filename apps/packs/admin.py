from apps.packs.models import Pack, OrgPack

from tenant_admin_site import admin_site

admin_site.register(Pack)
admin_site.register(OrgPack)
