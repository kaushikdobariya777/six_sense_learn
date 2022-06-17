# Generated by Django 2.2.4 on 2020-11-10 07:30

import common.file_storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('packs', '0001_create_packs'),
    ]

    operations = [
        migrations.AddField(
            model_name='pack',
            name='image',
            field=models.ImageField(blank=True, max_length=1024, null=True, storage=common.file_storage.TenantFileSystemS3Storage(), upload_to=''),
        ),
    ]