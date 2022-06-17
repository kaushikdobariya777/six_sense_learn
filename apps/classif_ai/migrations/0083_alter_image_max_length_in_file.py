# Generated by Django 2.2.4 on 2020-10-30 05:43

from django.db import migrations, models
from django_tenants.files.storage import TenantFileSystemStorage


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0082_alter_image_in_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='image',
            field=models.FileField(blank=True, max_length=1024, null=True, storage=TenantFileSystemStorage(), upload_to=''),
        ),
    ]
