# -*- coding: utf-8 -*-

from django.db import models
from django_model_cache import CacheManager
import uuid


class Brand(models.Model):
    name = models.CharField(max_length=128)

    cache = CacheManager(timeout=None)
    objects = models.Manager()

    class Meta:
        app_label = 'simple'


class Product(models.Model):
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    brand = models.ForeignKey('Brand', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    cache = CacheManager(fields=['code', ('brand_id', 'name')], related_fields=['brand'], timeout=None)
    # https://docs.djangoproject.com/en/1.11/topics/db/managers/#custom-managers-and-model-inheritance
    # If no managers are declared on a model and/or its parents
    # Django automatically creates the objects manager.
    objects = models.Manager()

    class Meta:
        unique_together = ('name', 'brand')
        app_label = 'simple'
