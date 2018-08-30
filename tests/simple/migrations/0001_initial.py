# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ('name', models.CharField(max_length=255)),
                ('brand', models.ForeignKey(to='simple.Brand')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='product',
            unique_together=set([('name', 'brand')]),
        ),
    ]
