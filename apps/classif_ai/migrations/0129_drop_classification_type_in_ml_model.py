# Generated by Django 3.2 on 2021-09-17 01:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0128_migrate_classification_type_from_ml_model_to_use_case'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mlmodel',
            name='classification_type',
        ),
    ]
