from django.contrib.postgres.operations import CreateExtension
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0116_switch_json_field'),
    ]

    operations = [
        CreateExtension('postgis'),
    ]
