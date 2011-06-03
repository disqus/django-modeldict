from django.db.models.signals import post_save, post_delete
from django.core.signals import request_finished

from modeldict.base import CachedDict, NoValue

class ModelDict(CachedDict):
    """
    Dictionary-style access to a model. Populates a cache and a local in-memory
    to avoid multiple hits to the database.
    
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

        self.key = key
        self.value = value

        self.model = model
        self.instances = instances
        self.auto_create = auto_create
        
        self.cache_key = 'ModelDict:%s:%s' % (model.__name__, self.key)
        self.last_updated_cache_key = 'ModelDict.last_updated:%s:%s' % (model.__name__, self.key)

        request_finished.connect(self._cleanup)
        post_save.connect(self._post_save, sender=model)
        post_delete.connect(self._post_delete, sender=model)
    
    def __setitem__(self, key, value):
        if isinstance(value, self.model):
            value = getattr(value, self.value)
        instance, created = self.model._default_manager.get_or_create(
            defaults={self.value: value},
            **{self.key: key}
        )
        
        # Ensure we're updating the value in the database if it changes, and
        # if it was frehsly created, we need to ensure we populate our cache.
        if getattr(instance, self.value) != value:
            # post_save hook hits so we dont need to populate
            setattr(instance, self.value, value)
            instance.save()
        elif created:
            self._populate(reset=True)
    
    def __delitem__(self, key):
        affected = self.model._default_manager.filter(**{self.key: key}).delete()
        # self._populate(reset=True)

    def setdefault(self, key, value):
        if isinstance(value, self.model):
            value = getattr(value, self.value)
        instance, created = self.model._default_manager.get_or_create(
            defaults={self.value: value},
            **{self.key: key}
        )
        self._populate(reset=True)
    
    def get_default(self, value):
        if not self.auto_create:
            return NoValue
        return self.model.objects.create(**{self.key: value})

    def _get_cache_data(self):
        qs = self.model._default_manager
        if self.instances:
            return dict((getattr(i, self.key), i) for i in qs.all())
        return dict(qs.values_list(self.key, self.value))

    # Signals

    def _post_save(self, sender, instance, created, **kwargs):
        if self._cache is None:
            self._populate()
        if self.instances:
            value = instance
        else:
            value = getattr(instance, self.value)
        key = getattr(instance, self.key)
        if value != self._cache.get(key):
            self._cache[key] = value
        self._populate(reset=True)
        
    def _post_delete(self, sender, instance, **kwargs):
        if self._cache:
            self._cache.pop(getattr(instance, self.key), None)
        self._populate(reset=True)