# Generated by Django 2.2.4 on 2020-09-27 22:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0074_add_unique_together_in_use_case_defect'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='mlmodeldefect',
            unique_together={('ml_model', 'defect')},
        ),
    ]