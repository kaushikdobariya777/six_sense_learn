# Generated by Django 2.2.4 on 2020-08-19 16:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0060_add_classification_corectness_to_file_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileregion',
            name='detection_correctness',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
