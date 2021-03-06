# Generated by Django 2.2.4 on 2020-08-10 14:28

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classif_ai', '0031_create_file_label'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileLabelHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('updated_ts', models.DateTimeField(auto_now=True, verbose_name='Last Updated Date')),
                ('is_user_feedback', models.BooleanField(default=True)),
                ('defect_info', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_filelabelhistory_created_related', to=settings.AUTH_USER_MODEL)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='file_label_history', to='classif_ai.File')),
                ('ml_model', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='file_label_history', to='classif_ai.MlModel')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_filelabelhistory_updated_related', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
