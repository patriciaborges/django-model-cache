# -*- coding: utf-8 -*-

from django.db import models
from django_model_cache import CacheController
import uuid


class Brand(models.Model):
    name = models.CharField(max_length=128)

    cache = CacheController(timeout=None)


class Product(models.Model):
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    brand = models.ForeignKey('Brand')
    name = models.CharField(max_length=255)

    cache = CacheController(fields=['code', ('brand_id', 'name')], related_fields=['brand'], timeout=None)

    class Meta:
        unique_together = ('name', 'brand')
