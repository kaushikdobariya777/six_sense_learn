# Generated by Django 2.2.4 on 2021-02-04 13:12

import common.file_storage
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0003_alter_default_of_file_set_meta_info_in_subscription'),
        ('classif_ai', '0095_add_subscription_in_use_case'),
    ]

    operations = [
        migrations.AddField(
            model_name='defect',
            name='subscription',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='defects', to='subscriptions.Subscription'),
            preserve_default=False,
        ),
    ]