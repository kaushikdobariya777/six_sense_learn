# Generated by Django 2.2.4 on 2020-08-06 05:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0025_alter_default_of_meta_info_in_fileset'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='file',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='fileset',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='mlmodel',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='uploadsession',
            options={'ordering': ['id']},
        ),
    ]
