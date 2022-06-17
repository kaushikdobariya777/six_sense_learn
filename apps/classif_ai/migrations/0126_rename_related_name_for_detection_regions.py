# Generated by Django 3.2 on 2021-09-16 15:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0125_add_ml_model_output_meta_info_to_model_detection_region'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gtdetectionregion',
            name='detection',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detection_regions', to='classif_ai.gtdetection'),
        ),
        migrations.AlterField(
            model_name='userdetectionregion',
            name='detection',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detection_regions', to='classif_ai.userdetection'),
        ),
    ]
