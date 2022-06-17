# Generated by Django 2.2.4 on 2020-07-29 07:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0013_create_uploadsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileset',
            name='upload_session',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.PROTECT, related_name='filesets', to='classif_ai.UploadSession'),
            preserve_default=False,
        ),
    ]