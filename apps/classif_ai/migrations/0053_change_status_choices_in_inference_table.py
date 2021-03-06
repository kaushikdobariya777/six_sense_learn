# Generated by Django 2.2.4 on 2020-08-12 19:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0052_create_file_set_inference_queue'),
    ]

    operations = [
        migrations.AlterField(
            model_name='filesetinferencequeue',
            name='status',
            field=models.CharField(choices=[('PENDING', 'PENDING'), ('PROCESSING', 'PROCESSING'), ('FINISHED', 'FINISHED'), ('FAILED', 'FAILED')], default='PENDING', max_length=50),
        ),
    ]
