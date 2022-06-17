# Generated by Django 2.2.4 on 2020-08-12 14:10

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classif_ai', '0045_add_blank_true_to_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='MlModelDefect',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('updated_ts', models.DateTimeField(auto_now=True, verbose_name='Last Updated Date')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_mlmodeldefect_created_related', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AlterField(
            model_name='defect',
            name='ml_models',
            field=models.ManyToManyField(related_name='defects', through='classif_ai.MlModelDefect', to='classif_ai.MlModel'),
        ),
        migrations.DeleteModel(
            name='ModelDefect',
        ),
        migrations.AddField(
            model_name='mlmodeldefect',
            name='defect',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classif_ai.Defect'),
        ),
        migrations.AddField(
            model_name='mlmodeldefect',
            name='ml_model',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classif_ai.MlModel'),
        ),
        migrations.AddField(
            model_name='mlmodeldefect',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_mlmodeldefect_updated_related', to=settings.AUTH_USER_MODEL),
        ),
    ]
