from django.contrib.auth import get_user_model

# Register your models here.
from apps.user_auth.models import BlackListedToken
from tenant_admin_site import admin_site

admin_site.register(get_user_model())
admin_site.register(BlackListedToken)
