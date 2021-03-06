# Generated by Django 2.2.4 on 2020-08-12 16:13

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0048_add_null_true_to_defect_ids'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fileregion',
            name='defect_ids',
        ),
        migrations.RemoveField(
            model_name='fileregionhistory',
            name='defect_ids',
        ),
        migrations.AddField(
            model_name='fileregion',
            name='defects',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='fileregionhistory',
            name='defects',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
    ]
