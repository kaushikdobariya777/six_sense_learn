# Generated by Django 2.2.4 on 2020-07-29 07:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0012_alter_blank_of_path_in_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
        ),
    ]
