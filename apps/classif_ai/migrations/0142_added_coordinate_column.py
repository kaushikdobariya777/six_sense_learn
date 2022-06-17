# Generated by Django 3.2 on 2022-01-19 07:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0141_add_image_path_to_wafermap'),
    ]

    operations = [
        migrations.AddField(
            model_name='wafermap',
            name='coordinate_meta_info',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='wafermap',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('auto_classified', 'Auto Classified'), ('manual_classification_pending', 'Manual classification pending'), ('manually_classified', 'Manually Classified')], default='manual_classification_pending', max_length=50),
        ),
    ]
