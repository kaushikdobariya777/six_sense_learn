from __future__ import unicode_literals

from django.contrib import admin
from django.conf import settings


class TenantAwareAdminSite(admin.AdminSite):
    def get_app_list(self, request):
        """override to return only the apps that are appropriate - tenant aware or public"""
        # check if current schema is public
        # TenantModel = get_tenant_model()
        # hostname = remove_www(request.get_host().split(":")[0]).lower()
        # tenant = self.get_tenant(TenantModel, hostname, request)
        # is_public = Organization.current_is_public(request)
        if request.tenant and request.tenant.schema_name == "public":
            is_public = True
        else:
            is_public = False

        app_list = super(TenantAwareAdminSite, self).get_app_list(request)
        tenant_aware_apps = []

        for app in app_list:
            if is_public:
                if "apps." + app["app_label"] in settings.SHARED_APPS:
                    tenant_aware_apps.append(app)
            else:
                if "apps." + app["app_label"] in settings.TENANT_APPS:
                    tenant_aware_apps.append(app)

        return tenant_aware_apps


# tenant aware admin site singleton
admin_site = TenantAwareAdminSite(name="admin")
