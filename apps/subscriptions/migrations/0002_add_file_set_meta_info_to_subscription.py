# Generated by Django 2.2.4 on 2020-07-31 07:31

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_create_subscriptions'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='file_set_meta_info',
            field=django.contrib.postgres.fields.jsonb.JSONField(default={}),
        ),
    ]
