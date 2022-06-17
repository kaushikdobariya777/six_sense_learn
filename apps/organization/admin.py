from django.contrib import admin

from apps.organization.forms import OrgForm
from apps.organization.models import Organization
from tenant_admin_site import admin_site


class OrganizationAdminModel(admin.ModelAdmin):
    # TODO: Get this working
    form = OrgForm
    list_display = ("schema_name", "name", "code")
    common_fields = ["schema_name", "name", "code"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + (
                "email",
                "password",
            )
        return self.readonly_fields

    def add_view(self, request, form_url="", extra_context=None):
        self.fields = self.common_fields + ["email", "password"]
        return super(OrganizationAdminModel, self).add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self.fields = self.common_fields
        return super(OrganizationAdminModel, self).change_view(request, object_id, form_url="", extra_context=None)

    def save_form(self, request, form, change):
        instance = super(OrganizationAdminModel, self).save_form(request, form, change)
        if change:
            instance.updated_by_id = request.user.id
        else:
            instance.created_by_id = request.user.id
        instance.save()
        return instance


admin_site.register(Organization, OrganizationAdminModel)
