from django.db import migrations


def forwards_func(apps, schema_editor):
    Organization = apps.get_model("organization", "Organization")
    OrganizationDomain = apps.get_model("organization", "OrganizationDomain")
    db_alias = schema_editor.connection.alias
    for org in Organization.objects.using(db_alias).all():
        OrganizationDomain.objects.using(db_alias).create(
            domain=org.domain_url, tenant=org, is_primary=True
        )


def backwards_func(apps, schema_editor):
    OrganizationDomain = apps.get_model("organization", "OrganizationDomain")
    Organization = apps.get_model("organization", "Organization")
    db_alias = schema_editor.connection.alias
    for org in OrganizationDomain.objects.using(db_alias).filter(is_primary=True):
        Organization.objects.filter(id=org.tenant_id).update(domain_url=org.domain)
    OrganizationDomain.objects.using(db_alias).all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0002_switch_to_django_tenants'),
    ]

    operations = [
        migrations.RunPython(forwards_func, backwards_func),
    ]
