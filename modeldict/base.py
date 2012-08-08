import time

from django.core.cache import cache

NoValue = object()


class CachedDict(object):
    def __init__(self, cache=cache, timeout=30):
        cls_name = type(self).__name__

        self._cache = None
        self._last_updated = None
        self.timeout = timeout
        self.cache = cache
        self.cache_key = cls_name
        self.last_updated_cache_key = '%s.last_updated' % (cls_name,)

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
        raise NotImplementedError

    def __delitem__(self, key):
        raise NotImplementedError

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
        return "<%s: %s>" % (self.__class__.__name__, self.model.__name__)

    def iteritems(self):
        self._populate()
        return self._cache.iteritems()

    def itervalues(self):
        self._populate()
        return self._cache.itervalues()

    def iterkeys(self):
        self._populate()
        return self._cache.iterkeys()

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

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
        if key not in self:
            self[key] = value

    def is_expired(self):
        if not self._last_updated:
            return True
        if time.time() > self._last_updated + self.timeout:
            return True
        return False

    def _populate(self, reset=False):
        self.cache.get(self.last_updated_cache_key)
        if reset:
            self._cache = None
        elif self._cache is None or self.is_expired():
            new_last_updated = self.cache.get(self.last_updated_cache_key) or 0
            self._cache = self.cache.get(self.cache_key)
            self._last_updated = new_last_updated

        if self._cache is None:
            self._update_cache_data()
        return self._cache

    def _update_cache_data(self):
        self._cache = self._get_cache_data()
        self._last_updated = int(time.time())
        self.cache.set(self.cache_key, self._cache)
        self.cache.set(self.last_updated_cache_key, self._last_updated)

    def _get_cache_data(self):
        raise NotImplementedError

    def _cleanup(self, *args, **kwargs):
        self._cache = None

    def clear_cache(self):
        self._cache = None

    def get_default(self, value):
        return NoValue
