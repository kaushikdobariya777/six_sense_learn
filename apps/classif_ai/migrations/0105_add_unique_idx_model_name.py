# Generated by Django 2.2.4 on 2021-03-16 05:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0104_merge_20210311_0536'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='name',
            field=models.CharField(blank=True, max_length=100, unique=True),
        ),
    ]