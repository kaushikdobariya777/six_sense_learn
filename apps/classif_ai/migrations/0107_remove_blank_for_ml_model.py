# Generated by Django 2.2.4 on 2021-04-06 04:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0106_add_unique_idx_usecase_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
