# Generated by Django 3.2 on 2021-11-23 09:36

import django.core.files.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0134_alter_mlmodel_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='wafermap',
            name='on_hold',
            field=models.BooleanField(default=True),
        )
    ]
