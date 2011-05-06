import time
from threading import local

from django.db.models.signals import post_save, post_delete
from django.core.signals import request_finished
from django.core.cache import cache

try:
    VERSION = __import__('pkg_resources') \
        .get_distribution('django-modeldict').version
except Exception, e:
    VERSION = 'unknown'

NoValue = object()

class ModelDict(local):
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
        >>> 'bar'
    
    If you want to use another key besides ``pk``, you may specify that in the
    constructor. However, this will be used as part of the cache key, so it's recommended
    to access it in the same way throughout your code.
    
        mydict = ModelDict(Model, key='foo', value='id')
        mydict['bar']
        >>> 'test'
    
    """
    def __init__(self, model, key='pk', value=None, instances=False, auto_create=False):
        assert value is not None

        self._cache = None
        self._last_updated = None

        self.model = model
        self.key = key
        self.value = value
        self.instances = instances
        self.auto_create = auto_create

        self.cache_key = 'ModelDict:%s:%s' % (model.__name__, key)
        self.last_updated_cache_key = 'ModelDict.last_updated:%s:%s' % (model.__name__, key)
        request_finished.connect(self._cleanup)
        post_save.connect(self._post_save, sender=model)
        post_delete.connect(self._post_delete, sender=model)
    
    # def __new__(cls, *args, **kwargs):
    #     self = super(ModelDict, cls).__new__(cls, *args, **kwargs)
    #     request_finished.connect(self._cleanup)
    #     return self
    
    def __getitem__(self, key):
        self._populate()
        try:
            return self._cache[key]
        except KeyError:
            value = self.get_default(key)
            if value is NoValue:
                raise
            return value
    
    def __setitem__(self, key, value):
        if isinstance(value, self.model):
            value = getattr(value, self.value)
        instance, created = self.model._default_manager.get_or_create(
            defaults={self.value: value},
            **{self.key: key}
        )
        if getattr(instance, self.value) != value:
            setattr(instance, self.value, value)
            instance.save()
        self._populate(reset=True)
    
    def __delitem__(self, key):
        self.model._default_manager.filter(**{self.key: key}).delete()
        self._populate(reset=True)
    
    def __len__(self):
        if self._cache is None:
            self._populate()
        return len(self._cache)
    
    def __contains__(self, key):
        self._populate()
        return key in self._cache

    def __iter__(self):
        self._populate()
        return iter(self._cache)
    
    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self)

    def __str__(self):
        return ''
        return ', '.join("%s=%s" % (k, v) for k, v in self.iteritems())

    def iteritems(self):
        self._populate()
        return self._cache.iteritems()
    
    def itervalues(self):
        self._populate()
        return self._cache.itervalues()
    
    def iterkeys(self):
        self._populate()
        return self._cache.iterkeys()
    
    def items(self):
        self._populate()
        return self._cache.items()
        
    def get(self, key, default=None):
        self._populate()
        return self._cache.get(key, default)
    
    def pop(self, key, default=NoValue):
        value = self.get(key, default)
        try:
            del self[key]
        except KeyError:
            pass
        return value
    
    def setdefault(self, key, value):
        if isinstance(value, self.model):
            value = getattr(value, self.value)
        instance, created = self.model._default_manager.get_or_create(
            defaults={self.value: value},
            **{self.key: key}
        )
        self._populate(reset=True)

    def _post_save(self, sender, instance, created, **kwargs):
        if self._cache is None:
            self._populate()
        if self.instances:
            self._cache[getattr(instance, self.key)] = instance
        else:
            self._cache[getattr(instance, self.key)] = getattr(instance, self.value)
        
    def _post_delete(self, sender, instance, **kwargs):
        if self._cache is None:
            self._populate()
        self._cache.pop(getattr(instance, self.key), None)

    def _populate(self, reset=False):
        if reset:
            self._cache = None
            # TODO: Race condition in updating last_updated.  Needs
            # a test + fix.
            self.last_updated = int(time.time())
            cache.set(self.last_updated_cache_key, self.last_updated)
        elif self._cache is None:
            new_last_updated = cache.get(self.last_updated_cache_key) or 0
            if new_last_updated > (self._last_updated or 0) or \
              not getattr(self, '_cache_stale', None):
                self._cache = cache.get(self.cache_key)
                self._last_updated = new_last_updated
            else:
                self._cache = self._cache_stale
                self._cache_stale = None
        if self._cache is None:
            qs = self.model._default_manager
            if self.instances:
                self._cache = dict((getattr(i, self.key), i) for i in qs.all())
            else:
                self._cache = dict(qs.values_list(self.key, self.value))
            cache.set(self.cache_key, self._cache)
        return self._cache    

    def _cleanup(self, *args, **kwargs):
        self._cache_stale = self._cache
        self._cache = None

    def get_default(self, value):
        if not self.auto_create:
            return NoValue
        return self.model.objects.create(**{self.key: value})
        