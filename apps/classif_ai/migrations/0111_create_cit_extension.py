from django.contrib.postgres.operations import CITextExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0110_add_index_to_name_in_file'),
    ]

    operations = [
        CITextExtension()
    ]
