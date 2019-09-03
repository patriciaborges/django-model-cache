from django.core.cache import caches
from django.db import models
from django.conf import settings

import json
import logging


def is_fetched(obj, relation_name):
    cache_name = '_{}_cache'.format(relation_name)
    return getattr(obj, cache_name, False)


class CacheManager(models.Manager):

    def __init__(self,
                 fields=set(),
                 related_fields=set(),
                 backend='default',
                 timeout=getattr(settings, 'CACHE_MODEL_TIMEOUT', None)
                 ):
        super(CacheManager, self).__init__()
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

    def get_multiple(self, key, queryset, timeout):
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

        pks = []
        for obj in queryset:
            pks.append(obj.pk)
            if obj.pk not in cache_hit_pks:
                self._save_cache(obj)
        self._cache.set(cache_key, json.dumps(pks), timeout=timeout)
        return queryset

    def delete_cache_multiple(self, key):
        cache_key = self._make_key_multiple(key)
        self._cache.delete(cache_key)

    def contribute_to_class(self, model, name):
        super(CacheManager, self).contribute_to_class(model, name)

        def load_related(instance, *args):
            related_fields = args if args else self.related_fields
            for field in related_fields:
                if not is_fetched(instance, field):
                    model_field = self.model._meta.get_field(field)
                    related_pk = getattr(instance, model_field.attname)
                    RemoteModel = model_field.remote_field.model
                    related_instance = None
                    if related_pk:
                        try:
                            manager = RemoteModel.cache
                        except AttributeError:
                            manager = RemoteModel._default_manager
                        related_instance = manager.get(pk=related_pk)

                    setattr(instance, model_field.get_cache_name(), related_instance)

        self.model.load_related = load_related

        models.signals.post_save.connect(self._post_save, sender=model)
        models.signals.post_delete.connect(self._post_delete, sender=model)

    def _get_from_cache(self, **kwargs):
        key = self._make_key(**kwargs)
        return self._cache.get(key)

    def _get_from_db(self, **kwargs):
        obj = self.model.objects.get(**kwargs)
        self._save_cache(obj)
        return obj

    def _save_cache(self, instance):
        instance.load_related()

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
                self._cache.set(key, instance, timeout=self.timeout)

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

    def _post_save(self, instance, **kwargs):
        self._save_cache(instance)

    def _post_delete(self, instance, **kwargs):
        self._delete_cache(instance)
