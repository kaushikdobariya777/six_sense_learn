# Generated by Django 2.2.4 on 2020-12-10 22:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0093_auto_20201209_1427'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mlmodel',
            name='type',
        ),
        migrations.AddField(
            model_name='usecase',
            name='type',
            field=models.CharField(choices=[('DETECTION', 'Detection'), ('CLASSIFICATION', 'Classification'), ('CLASSIFICATION_AND_DETECTION', 'Detection and Classification')], default='DETECTION', max_length=64),
        ),
    ]
