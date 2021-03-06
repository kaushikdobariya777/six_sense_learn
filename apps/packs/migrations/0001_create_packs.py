# Generated by Django 2.2.4 on 2020-07-15 11:00

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0001_create_sub_organization_and_organization_user'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgPack',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('updated_ts', models.DateTimeField(auto_now=True, verbose_name='Last Updated Date')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='packs_orgpack_created_related', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Pack',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True, verbose_name='Created Date')),
                ('updated_ts', models.DateTimeField(auto_now=True, verbose_name='Last Updated Date')),
                ('name', models.CharField(blank=True, default='', max_length=100)),
                ('type', models.CharField(blank=True, default='Public', max_length=100)),
                ('is_demo', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='packs_pack_created_related', to=settings.AUTH_USER_MODEL)),
                ('sub_organizations', models.ManyToManyField(related_name='packs', through='packs.OrgPack', to='users.SubOrganization')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='packs_pack_updated_related', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='orgpack',
            name='pack',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='packs.Pack'),
        ),
        migrations.AddField(
            model_name='orgpack',
            name='sub_organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='users.SubOrganization'),
        ),
        migrations.AddField(
            model_name='orgpack',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='packs_orgpack_updated_related', to=settings.AUTH_USER_MODEL),
        ),
    ]
