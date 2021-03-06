# Generated by Django 2.2.4 on 2020-08-12 11:39

from django.conf import settings
import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classif_ai', '0042_create_file_region'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedbackFileRegionHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('updated_ts', models.DateTimeField(auto_now=True, verbose_name='Last Updated Date')),
                ('defect_ids', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None)),
                ('region', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('is_user_feedback', models.BooleanField(default=False)),
                ('ai_region', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='feedback_file_region_history', to='classif_ai.FileRegion')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_feedbackfileregionhistory_created_related', to=settings.AUTH_USER_MODEL)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='feedback_file_region_history', to='classif_ai.File')),
                ('ml_model', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='feedback_file_region_history', to='classif_ai.MlModel')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_feedbackfileregionhistory_updated_related', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
