# Generated by Django 2.2.4 on 2021-04-21 07:06

import django.contrib.postgres.fields.citext
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0111_create_cit_extension'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='name',
            field=django.contrib.postgres.fields.citext.CITextField(max_length=100, unique=True),
        ),
    ]
