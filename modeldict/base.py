import time

from django.core.cache import cache

NoValue = object()


class CachedDict(object):
    def __init__(self, cache=cache, timeout=30):
        cls_name = type(self).__name__

        self._local_cache = None
        self._last_checked_for_remote_changes = None
        self.timeout = timeout

        self.remote_cache = cache
        self.remote_cache_key = cls_name
        self.remote_cache_last_updated_key = '%s.last_updated' % (cls_name,)

    def __getitem__(self, key):
        self._populate()

        try:
            return self._local_cache[key]
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
        if self._local_cache is None:
            self._populate()

        return len(self._local_cache)

    def __contains__(self, key):
        self._populate()
        return key in self._local_cache

    def __iter__(self):
        self._populate()
        return iter(self._local_cache)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.model.__name__)

    def iteritems(self):
        self._populate()
        return self._local_cache.iteritems()

    def itervalues(self):
        self._populate()
        return self._local_cache.itervalues()

    def iterkeys(self):
        self._populate()
        return self._local_cache.iterkeys()

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def items(self):
        self._populate()
        return self._local_cache.items()

    def get(self, key, default=None):
        self._populate()
        return self._local_cache.get(key, default)

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

    def local_cache_has_expired(self):
        """
        Returns ``True`` if the in-memory cache has expired (based on
        the cached _last_checked_for_remote_changes value).
        """
        proc_last_updated = self._last_checked_for_remote_changes

        if not proc_last_updated:
            return True

        return time.time() > proc_last_updated + self.timeout

    def remote_has_changed(self):
        """
        Returns ``True`` if the global cache has changed (based on
        the remote_cache_last_updated_key value).

        A return value of ``None`` signifies that no data was available.
        """
        cache_last_updated = self.remote_cache.get(self.remote_cache_last_updated_key)

        if not cache_last_updated:
            return None

        return int(cache_last_updated) > self._last_checked_for_remote_changes

    def get_cache_data(self):
        """
        Pulls data from the cache backend.
        """
        return self._get_cache_data()

    def clear_cache(self):
        """
        Clears the in-process cache.
        """
        self._local_cache = None
        self._last_checked_for_remote_changes = None

    def _populate(self, reset=False):
        """
        Ensures the cache is populated and still valid.

        The cache is checked when:

        - The local timeout has been reached
        - The local cache is not set

        The cache is invalid when:

        - The global cache has expired (via remote_cache_last_updated_key)
        """
        if reset:
            self._local_cache = None
        elif self.local_cache_has_expired():
            now = int(time.time())

            # Avoid hitting memcache if we dont have a local cache
            if self._local_cache is None:
                global_changed = True
            else:
                global_changed = self.remote_has_changed()

            # If the cache is expired globally, or local cache isnt present
            if global_changed or self._local_cache is None:
                # The value may or may not exist in the cache
                self._local_cache = self.remote_cache.get(self.remote_cache_key)

                # If for some reason remote_cache_last_updated_key was None (but the cache key wasnt)
                # we should force the key to exist to prevent continuous calls
                if global_changed is None and self._local_cache is not None:
                    self.remote_cache.add(self.remote_cache_last_updated_key, now)

            self._last_checked_for_remote_changes = now

        if self._local_cache is None:
            self._update_cache_data()

        return self._local_cache

    def _update_cache_data(self):
        self._local_cache = self.get_cache_data()
        self._last_checked_for_remote_changes = int(time.time())
        # We only set remote_cache_last_updated_key when we know the cache is current
        # because setting this will force all clients to invalidate their cached
        # data if it's newer
        self.remote_cache.set(self.remote_cache_key, self._local_cache)
        self.remote_cache.set(self.remote_cache_last_updated_key, self._last_checked_for_remote_changes)

    def _get_cache_data(self):
        raise NotImplementedError

    def _cleanup(self, *args, **kwargs):
        # We set _last_updated to a false value to ensure we hit the last_updated cache
        # on the next request
        self._last_checked_for_remote_changes = None
