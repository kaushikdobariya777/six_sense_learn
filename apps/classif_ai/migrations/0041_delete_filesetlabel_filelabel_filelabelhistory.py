# Generated by Django 2.2.4 on 2020-08-12 11:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0040_add_null_true_to_defects'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='filelabelhistory',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='filelabelhistory',
            name='file',
        ),
        migrations.RemoveField(
            model_name='filelabelhistory',
            name='file_set_label',
        ),
        migrations.RemoveField(
            model_name='filelabelhistory',
            name='updated_by',
        ),
        migrations.AlterUniqueTogether(
            name='filesetlabel',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='filesetlabel',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='filesetlabel',
            name='file_set',
        ),
        migrations.RemoveField(
            model_name='filesetlabel',
            name='ml_model',
        ),
        migrations.RemoveField(
            model_name='filesetlabel',
            name='updated_by',
        ),
        migrations.DeleteModel(
            name='FileLabel',
        ),
        migrations.DeleteModel(
            name='FileLabelHistory',
        ),
        migrations.DeleteModel(
            name='FileSetLabel',
        ),
    ]
