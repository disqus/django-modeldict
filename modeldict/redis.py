from django.core.signals import request_finished

from modeldict.base import CachedDict


class RedisDict(CachedDict):
    """
    Dictionary-style access to a redis hash table. Populates a cache and a local
    in-memory to avoid multiple hits to the database.

    Functions just like you'd expect it::

        mydict = RedisDict('my_redis_key', Redis())
        mydict['test']
        >>> 'bar' #doctest: +SKIP

    """
    def __init__(self, keyspace, connection, *args, **kwargs):
        super(CachedDict, self).__init__(*args, **kwargs)

        self.keyspace = keyspace
        self.conn = connection

        self.cache_key = 'RedisDict:%s' % (keyspace,)
        self.last_updated_cache_key = 'RedisDict.last_updated:%s' % (keyspace,)

        request_finished.connect(self._cleanup)

    def __setitem__(self, key, value):
        self.conn.hset(self.keyspace, key, value)
        if value != self._cache.get(key):
            self._cache[key] = value
        self._populate(reset=True)

    def __delitem__(self, key):
        self.conn.hdel(self.keyspace, key)
        self._cache.pop(key)
        self._populate(reset=True)

    def _get_cache_data(self):
        return self.conn.hgetall(self.keyspace)
