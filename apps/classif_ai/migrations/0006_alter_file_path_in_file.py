# Generated by Django 2.2.4 on 2020-07-28 02:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0005_add_file_related_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='file_path',
            field=models.CharField(max_length=255),
        ),
    ]
