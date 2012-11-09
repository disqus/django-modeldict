import time

from django.core.cache import cache

NoValue = object()


class CachedDict(object):
    def __init__(self, cache=cache, timeout=30):
        cls_name = type(self).__name__

        self._local_cache = None
        self._local_last_updated = None

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
        Returns ``True`` if the in-memory cache has expired.
        """
        if not self._last_checked_for_remote_changes:
            return True  # Never checked before

        recheck_at = self._last_checked_for_remote_changes + self.timeout
        return time.time() > recheck_at

    def local_cache_is_invalid(self):
        """
        Returns ``True`` if the local cache is invalid and needs to be
        refreshed with data from the remote cache.

        A return value of ``None`` signifies that no data was available.
        """
        # If the local_cache is empty, avoid hitting memcache entirely
        if self._local_cache is None:
            return True

        remote_last_updated = self.remote_cache.get(
            self.remote_cache_last_updated_key
        )

        if not remote_last_updated:
            # TODO: I don't like how we're overloading the return value here for
            # this method.  It would be better to have a separate method or
            # @property that is the remote last_updated value.
            return None  # Never been updated

        return int(remote_last_updated) > self._local_last_updated

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
        self._local_last_updated = None
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
        now = int(time.time())

        # If asked to reset, then simply set local cache to None
        if reset:
            self._local_cache = None
        # Otherwise, if the local cache has expired, we need to go check with
        # our remote last_updated value to see if the dict values have changed.
        elif self.local_cache_has_expired():

            local_cache_is_invalid = self.local_cache_is_invalid()

            # If local_cache_is_invalid  is None, that means that there was no
            # data present, so we assume we need to add the key to cache.
            if local_cache_is_invalid is None:
                self.remote_cache.add(self.remote_cache_last_updated_key, now)

            # Now, if the remote has changed OR it was None in the first place,
            # pull in the values from the remote cache and set it to the
            # local_cache
            if local_cache_is_invalid or local_cache_is_invalid is None:
                self._local_cache = self.remote_cache.get(self.remote_cache_key)

            # No matter what, we've updated from remote, so mark ourselves as
            # such so that we won't expire until the next timeout
            self._local_last_updated = now

        # Update from cache if local_cache is still empty
        if self._local_cache is None:
            self._update_cache_data()

        # No matter what happened, we last checked for remote changes just now
        self._last_checked_for_remote_changes = now

        return self._local_cache

    def _update_cache_data(self):
        self._local_cache = self.get_cache_data()

        now = int(time.time())
        self._local_last_updated = now
        self._last_checked_for_remote_changes = now

        # We only set remote_cache_last_updated_key when we know the cache is
        # current because setting this will force all clients to invalidate
        # their cached data if it's newer
        self.remote_cache.set(self.remote_cache_key, self._local_cache)
        self.remote_cache.set(
            self.remote_cache_last_updated_key,
            self._last_checked_for_remote_changes
        )

    def _get_cache_data(self):
        raise NotImplementedError

    def _cleanup(self, *args, **kwargs):
        # We set _last_updated to a false value to ensure we hit the
        # last_updated cache on the next request
        self._last_checked_for_remote_changes = None
