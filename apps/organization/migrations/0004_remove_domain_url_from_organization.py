from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0003_migrate_domains_urls_to_organizationdomain'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='organization',
            name='domain_url',
        ),
    ]
