# Generated by Django 2.2.4 on 2021-01-08 04:27

import common.file_storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0092_add_is_bookmarked_to_file_set'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileset',
            name='is_bookmarked',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
