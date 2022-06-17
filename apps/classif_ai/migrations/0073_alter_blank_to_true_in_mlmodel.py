# Generated by Django 2.2.4 on 2020-09-27 22:27

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0072_add_dataset_train_type_and_belongs_to_old_model_training_data_to_training_session_file_set'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='path',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='mlmodel',
            name='training_performance_metrics',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict),
        ),
    ]