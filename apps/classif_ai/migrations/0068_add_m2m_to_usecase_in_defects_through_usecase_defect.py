# Generated by Django 2.2.4 on 2020-09-07 11:47

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classif_ai', '0067_add_fk_to_usecase_in_mlmodel'),
    ]

    operations = [
        migrations.CreateModel(
            name='UseCaseDefect',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('updated_ts', models.DateTimeField(auto_now=True, verbose_name='Last Updated Date')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_usecasedefect_created_related', to=settings.AUTH_USER_MODEL)),
                ('defect', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='use_case_defects', to='classif_ai.Defect')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classif_ai_usecasedefect_updated_related', to=settings.AUTH_USER_MODEL)),
                ('use_case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='use_case_defects', to='classif_ai.UseCase')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='defect',
            name='use_case',
            field=models.ManyToManyField(related_name='defects', through='classif_ai.UseCaseDefect', to='classif_ai.UseCase'),
        ),
    ]