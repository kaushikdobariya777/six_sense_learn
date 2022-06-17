# Generated by Django 2.2.4 on 2020-08-03 04:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0002_add_file_set_meta_info_to_subscription'),
        ('classif_ai', '0019_add_fk_to_subscription_in_uploadsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='mlmodel',
            name='subscription',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.PROTECT, related_name='ml_models', to='subscriptions.Subscription'),
            preserve_default=False,
        ),
    ]
