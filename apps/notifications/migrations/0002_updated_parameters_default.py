# Generated by Django 3.2 on 2021-12-29 10:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_added_notification_and_scenario_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='parameters',
            field=models.JSONField(default=dict, blank=True),
        ),
        migrations.AlterField(
            model_name='notification',
            name='scenario',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notification_scenario', to='notifications.notificationscenario'),
        ),
    ]
