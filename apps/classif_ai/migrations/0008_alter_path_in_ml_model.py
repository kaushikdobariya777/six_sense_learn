# Generated by Django 2.2.4 on 2020-07-28 02:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0007_rename_file_path_to_path_in_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='path',
            field=models.CharField(max_length=255),
        ),
    ]
