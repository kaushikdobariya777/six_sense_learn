# Generated by Django 2.2.4 on 2021-04-19 11:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0107_remove_blank_for_ml_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadsession',
            name='is_bookmarked',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
