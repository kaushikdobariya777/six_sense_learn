# Generated by Django 2.2.4 on 2020-10-09 08:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0076_merge_20201009_0807'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mlmodel',
            name='status',
            field=models.CharField(choices=[('training', 'Training'), ('ready_for_deployment', 'Ready for Deployment'), ('training_failed', 'Training failed'), ('deployed_in_prod', 'Deployed in production')], max_length=50),
        ),
    ]
