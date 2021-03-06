# Generated by Django 2.2.4 on 2020-12-11 10:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0094_alter_blank_meta_info_in_file_set'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='file_set',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='classif_ai.FileSet'),
        ),
        migrations.AlterField(
            model_name='fileregion',
            name='file',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_regions', to='classif_ai.File'),
        ),
        migrations.AlterField(
            model_name='fileregionhistory',
            name='file',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_region_history', to='classif_ai.File'),
        ),
        migrations.AlterField(
            model_name='fileregionhistory',
            name='file_region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_region_history', to='classif_ai.FileRegion'),
        ),
        migrations.AlterField(
            model_name='filesetinferencequeue',
            name='file_set',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_set_inference_queues', to='classif_ai.FileSet'),
        ),
    ]
