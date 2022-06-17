# Generated by Django 3.0.9 on 2021-07-14 05:30

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0005_add_blank_for_overkill_defect_config'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='file_set_meta_info',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict),
        ),
    ]
