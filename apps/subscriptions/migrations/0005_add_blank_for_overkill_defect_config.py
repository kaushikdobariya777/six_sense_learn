# Generated by Django 2.2.4 on 2021-04-26 05:13

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0004_add_overkill_config_to_subscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='overkill_defect_config',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), blank=True, default=list, size=None),
        ),
    ]
