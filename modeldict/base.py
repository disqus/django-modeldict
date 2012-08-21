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

    def get_default(self, key):
        return NoValue

    def is_local_expired(self):
        """
        Returns ``True`` if the in-memory cache has expired (based on
        the cached last_updated value).
        """
        proc_last_updated = self._last_updated
        if not proc_last_updated:
            return True

        if time.time() > proc_last_updated + self.timeout:
            return True

        return False

    def has_global_changed(self):
        """
        Returns ``True`` if the global cache has changed (based on
        the last_updated_cache_key value).

        A return value of ``None`` signifies that no data was available.
        """
        cache_last_updated = self.cache.get(self.last_updated_cache_key)
        if not cache_last_updated:
            return None

        if int(cache_last_updated) > self._last_updated:
            return True

        return False

    def get_cache_data(self):
        """
        Pulls data from the cache backend.
        """
        return self._get_cache_data()

    def clear_cache(self):
        """
        Clears the in-process cache.
        """
        self._cache = None
        self._last_updated = None

    def _populate(self, reset=False):
        """
        Ensures the cache is populated and still valid.

        The cache is checked when:

        - The local timeout has been reached
        - The local cache is not set

        The cache is invalid when:

        - The global cache has expired (via last_updated_cache_key)
        """
        if reset:
            self._cache = None
        elif self.is_local_expired():
            now = int(time.time())
            # Avoid hitting memcache if we dont have a local cache
            if self._cache is None:
                global_changed = True
            else:
                global_changed = self.has_global_changed()

            # If the cache is expired globally, or local cache isnt present
            if global_changed or self._cache is None:
                # The value may or may not exist in the cache
                self._cache = self.cache.get(self.cache_key)

                # If for some reason last_updated_cache_key was None (but the cache key wasnt)
                # we should force the key to exist to prevent continuous calls
                if global_changed is None and self._cache is not None:
                    self.cache.add(self.last_updated_cache_key, now)

            self._last_updated = now

        if self._cache is None:
            self._update_cache_data()
        return self._cache

    def _update_cache_data(self):
        self._cache = self.get_cache_data()
        self._last_updated = int(time.time())
        # We only set last_updated_cache_key when we know the cache is current
        # because setting this will force all clients to invalidate their cached
        # data if it's newer
        self.cache.set(self.cache_key, self._cache)
        self.cache.set(self.last_updated_cache_key, self._last_updated)

    def _get_cache_data(self):
        raise NotImplementedError

    def _cleanup(self, *args, **kwargs):
        # We set _last_updated to a false value to ensure we hit the last_updated cache
        # on the next request
        self._last_updated = None
