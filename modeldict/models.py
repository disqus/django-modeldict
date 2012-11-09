from django.db.models.signals import post_save, post_delete
from django.core.signals import request_finished

from modeldict.base import CachedDict, NoValue


try:
    from celery.signals import task_postrun
except ImportError:  # celery must not be installed
    has_celery = False
else:
    has_celery = True


class ModelDict(CachedDict):
    """
    Dictionary-style access to a model. Populates a cache and a local in-memory
    store to avoid multiple hits to the database.

    Specifying ``instances=True`` will cause the cache to store instances rather
    than simple values.

    If ``auto_create=True`` accessing modeldict[key] when key does not exist will
    attempt to create it in the database.

    Functions in two different ways, depending on the constructor:

        # Given ``Model`` that has a column named ``foo`` where the value is "bar":

        mydict = ModelDict(Model, value='foo')
        mydict['test']
        >>> 'bar' #doctest: +SKIP

    If you want to use another key besides ``pk``, you may specify that in the
    constructor. However, this will be used as part of the cache key, so it's recommended
    to access it in the same way throughout your code.

        mydict = ModelDict(Model, key='foo', value='id')
        mydict['bar']
        >>> 'test' #doctest: +SKIP

    """
    def __init__(self, model, key='pk', value=None, instances=False, auto_create=False, *args, **kwargs):
        assert value is not None

        super(ModelDict, self).__init__(*args, **kwargs)

        cls_name = type(self).__name__
        model_name = model.__name__

        self.key = key
        self.value = value

        self.model = model
        self.instances = instances
        self.auto_create = auto_create

        self.remote_cache_key = '%s:%s:%s' % (cls_name, model_name, self.key)
        self.remote_cache_last_updated_key = '%s.last_updated:%s:%s' % (cls_name, model_name, self.key)

        request_finished.connect(self._cleanup)
        post_save.connect(self._post_save, sender=model)
        post_delete.connect(self._post_delete, sender=model)

        if has_celery:
            task_postrun.connect(self._cleanup)

    def __setitem__(self, key, value):
        if isinstance(value, self.model):
            value = getattr(value, self.value)

        manager = self.model._default_manager
        instance, created = manager.get_or_create(
            defaults={self.value: value},
            **{self.key: key}
        )

        # Ensure we're updating the value in the database if it changes
        if getattr(instance, self.value) != value:
            setattr(instance, self.value, value)
            manager.filter(**{self.key: key}).update(**{self.value: value})
            self._post_save(sender=self.model, instance=instance, created=False)

    def __delitem__(self, key):
        self.model._default_manager.filter(**{self.key: key}).delete()
        # self._populate(reset=True)

    def setdefault(self, key, value):
        if isinstance(value, self.model):
            value = getattr(value, self.value)

        instance, created = self.model._default_manager.get_or_create(
            defaults={self.value: value},
            **{self.key: key}
        )

    def get_default(self, key):
        if not self.auto_create:
            return NoValue
        result = self.model.objects.get_or_create(**{self.key: key})[0]
        if self.instances:
            return result
        return getattr(result, self.value)

    def _get_cache_data(self):
        qs = self.model._default_manager
        if self.instances:
            return dict((getattr(i, self.key), i) for i in qs.all())
        return dict(qs.values_list(self.key, self.value))

    # Signals

    def _post_save(self, sender, instance, created, **kwargs):
        self._populate(reset=True)

    def _post_delete(self, sender, instance, **kwargs):
        self._populate(reset=True)
