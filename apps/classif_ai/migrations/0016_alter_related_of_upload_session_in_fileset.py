# Generated by Django 2.2.4 on 2020-07-30 11:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0015_add_base_to_all_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileset',
            name='upload_session',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='file_sets', to='classif_ai.UploadSession'),
        ),
    ]
