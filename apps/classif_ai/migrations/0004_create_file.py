# Generated by Django 2.2.4 on 2020-07-27 09:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0003_create_fileset'),
    ]

    operations = [
        migrations.CreateModel(
            name='File',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100)),
                ('file_path', models.FilePathField(max_length=255)),
                ('file_set_id', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='classif_ai.FileSet')),
            ],
        ),
    ]
