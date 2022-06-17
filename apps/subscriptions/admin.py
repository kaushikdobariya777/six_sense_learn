# Register your models here.
from apps.subscriptions.models import Subscription
from tenant_admin_site import admin_site

admin_site.register(Subscription)
