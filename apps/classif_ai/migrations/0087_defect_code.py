# Generated by Django 2.2.4 on 2020-11-16 12:30

import common.file_storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0086_file_region_model_output_meta_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='defect',
            name='code',
            field=models.SlugField(blank=True, max_length=100),
        ),
    ]