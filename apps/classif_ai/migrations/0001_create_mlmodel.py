# Generated by Django 2.2.4 on 2020-07-27 09:34

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MlModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100)),
                ('path', models.FilePathField(allow_folders=True, max_length=255)),
                ('input_format', django.contrib.postgres.fields.jsonb.JSONField()),
                ('output_format', django.contrib.postgres.fields.jsonb.JSONField()),
                ('code', models.CharField(max_length=100)),
                ('version', models.IntegerField()),
                ('status', models.CharField(choices=[('Active', 'Active'), ('Inactive', 'Inactive')], max_length=50)),
                ('is_stable', models.BooleanField(default=True)),
            ],
            options={
                'unique_together': {('code', 'version')},
            },
        ),
    ]