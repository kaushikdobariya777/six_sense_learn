# Generated by Django 2.2.4 on 2020-11-21 00:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0088_add_unique_index_to_code_in_defect'),
    ]

    operations = [
        migrations.AlterField(
            model_name='defect',
            name='name',
            field=models.CharField(blank=True, max_length=100, unique=True),
        ),
    ]
