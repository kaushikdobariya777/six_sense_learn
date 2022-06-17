# Generated by Django 2.2.4 on 2020-08-12 13:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0043_create_feedback_file_region_history'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackfileregionhistory',
            name='file_region',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.PROTECT, related_name='feedback_file_region_history', to='classif_ai.FileRegion'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='feedbackfileregionhistory',
            name='ai_region',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ai_file_region_history', to='classif_ai.FileRegion'),
        ),
    ]
