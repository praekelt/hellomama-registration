# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-07-06 09:44
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0005_subscriptionrequest_metadata'),
    ]

    operations = [
        migrations.RenameField(
            model_name='subscriptionrequest',
            old_name='contact',
            new_name='identity',
        ),
    ]
