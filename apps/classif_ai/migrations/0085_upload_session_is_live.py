# Generated by Django 2.2.4 on 2020-11-10 08:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0084_fileset_is_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadsession',
            name='is_live',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]