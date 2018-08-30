from django.core.cache import caches
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.manager import ManagerDescriptor
from django.db import models
from django.conf import settings

import json
import logging


class CacheController(object):

    def __init__(self,
                 fields=set(),
                 related_fields=set(),
                 backend='default',
                 timeout=getattr(settings, 'CACHE_MODEL_TIMEOUT', None)
                 ):
        self._cache = caches[backend]
        self.fields = set(fields)
        self.fields.add('pk')
        self.related_fields = related_fields
        self.timeout = timeout

    def get(self, force_db=False, **kwargs):
        if self.model._meta.pk.name in kwargs:
            kwargs['pk'] = kwargs[self.model._meta.pk.name]
            del kwargs[self.model._meta.pk.name]

        if not force_db:
            obj = self._get_from_cache(**kwargs)
            if obj:
                logging.debug("cache hit {} {}".format(self.model, kwargs))
                return obj
        logging.debug("cache miss {} {}".format(self.model, kwargs))
        return self._get_from_db(**kwargs)

    def get_or_none(self, *args, **kwargs):
        try:
            return self.get(*args, **kwargs)
        except self.model.DoesNotExist:
            return None

    def get_multiple(self, key, make_qs, timeout):
        cache_key = self._make_key_multiple(key)
        cached_multiple_value = self._cache.get(cache_key)
        cache_hit_pks = set([])
        has_cache_miss = False

        if cached_multiple_value:
            multiple_obj = json.loads(cached_multiple_value)
            result = []
            for pk in multiple_obj:
                obj_from_cache = self._get_from_cache(pk=pk)
                if obj_from_cache is not None:
                    result.append(obj_from_cache)
                    cache_hit_pks.add(pk)
                else:
                    has_cache_miss = True
            if not has_cache_miss:
                return result

        objs = make_qs()
        pks = []
        for obj in objs:
            pks.append(obj.pk)
            if obj.pk not in cache_hit_pks:
                self._save_cache(obj)
        self._cache.set(cache_key, json.dumps(pks), timeout=timeout)
        return objs

    def delete_cache_multiple(self, key):
        cache_key = self._make_key_multiple(key)
        self._cache.delete(cache_key)

    def contribute_to_class(self, model, name):
        self.model = model

        if self.related_fields:
            def load_related(instance, *args):
                related_fields = args if args else self.related_fields
                for field in related_fields:
                    model_field = self.model._meta.get_field_by_name(field)[0]
                    related_pk = getattr(instance, model_field.attname)
                    related_instance = model_field.rel.to.cache.get(pk=related_pk) if related_pk else None
                    setattr(instance, model_field.get_cache_name(), related_instance)

            self.model.load_related = load_related
        setattr(model, name, ManagerDescriptor(self))

        models.signals.post_save.connect(self._post_save, sender=model)
        models.signals.post_delete.connect(self._post_delete, sender=model)

    def _get_from_cache(self, **kwargs):
        key = self._make_key(**kwargs)
        cached_value = self._cache.get(key)
        return self._deserialize(cached_value) if cached_value else None

    def _get_from_db(self, **kwargs):
        obj = self.model.objects.get(**kwargs)
        self._save_cache(obj)
        return obj

    def _save_cache(self, instance):
        serialized_obj = self._serialize(instance)

        for field in self.fields:
            if type(field) is tuple:
                kwargs = {}
                for item in field:
                    kwargs[item] = getattr(instance, item)
                key = self._make_key(**kwargs) if kwargs else None
            else:
                value = getattr(instance, field)
                key = self._make_key(**{field: value}) if value else None
            if key:
                self._cache.set(key, serialized_obj, timeout=self.timeout)

    def _delete_cache(self, instance):
        for field in self.fields:
            if type(field) is tuple:
                kwargs = {}
                for item in field:
                    kwargs[item] = getattr(instance, item)
                key = self._make_key(**kwargs)
            else:
                value = getattr(instance, field)
                key = self._make_key(**{field: value}) if value else None
            if key:
                self._cache.delete(key)

    def _make_key_multiple(self, key):
        return "{app}.{class_name}.objects.{key}".format(
            app=self.model._meta.app_label,
            class_name=self.model.__name__,
            key=key
        )

    def _make_key(self, **kwargs):
        for k, v in kwargs.items():
            kwargs[k] = str(v)
        query = tuple(sorted(kwargs.items()))
        query = hash(query)
        return "{app}.{cls_name}.{query}".format(
            app=self.model._meta.app_label, cls_name=self.model.__name__, query=query)

    def _serialize(self, obj):
        from django.db.models.fields.files import FileField

        dict_obj = {}
        for field in self.model._meta.local_fields:
            value = getattr(obj, field.attname)
            if isinstance(field, FileField):
                dict_obj[field.attname] = value.name
                continue
            dict_obj[field.attname] = value

        return json.dumps(dict_obj, cls=DjangoJSONEncoder)

    def _deserialize(self, data):
        obj = json.loads(data)

        instance = self.model()

        for field in self.model._meta.local_fields:
            if field.attname in obj:
                setattr(instance, field.attname, field.to_python(obj[field.attname]))
            else:
                return None
        return instance

    def _post_save(self, instance, **kwargs):
        self._save_cache(instance)

    def _post_delete(self, instance, **kwargs):
        self._delete_cache(instance)
