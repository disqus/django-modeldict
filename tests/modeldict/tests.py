from __future__ import absolute_import

import mock
import time

from django.core.cache import cache
from django.core.signals import request_finished
from django.test import TestCase, TransactionTestCase

from modeldict import ModelDict
from modeldict.base import CachedDict
from .models import ModelDictModel


class ModelDictTest(TransactionTestCase):
    # XXX: uses transaction test due to request_finished signal causing a rollback
    urls = 'tests.modeldict.urls'

    def setUp(self):
        cache.clear()

    def assertHasReceiver(self, signal, function):
        for ident, reciever in signal.receivers:
            if reciever() is function:
                return True
        return False

    def test_api(self):
        base_count = ModelDictModel.objects.count()

        mydict = ModelDict(ModelDictModel, key='key', value='value')
        mydict['foo'] = 'bar'
        self.assertEquals(mydict['foo'], 'bar')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar')
        self.assertEquals(ModelDictModel.objects.count(), base_count + 1)
        mydict['foo'] = 'bar2'
        self.assertEquals(mydict['foo'], 'bar2')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar2')
        self.assertEquals(ModelDictModel.objects.count(), base_count + 1)
        mydict['foo2'] = 'bar'
        self.assertEquals(mydict['foo2'], 'bar')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo2'), 'bar')
        self.assertEquals(ModelDictModel.objects.count(), base_count + 2)
        del mydict['foo2']
        self.assertRaises(KeyError, mydict.__getitem__, 'foo2')
        self.assertFalse(ModelDictModel.objects.filter(key='foo2').exists())
        self.assertEquals(ModelDictModel.objects.count(), base_count + 1)

        ModelDictModel.objects.create(key='foo3', value='hello')

        self.assertEquals(mydict['foo3'], 'hello')
        self.assertTrue(ModelDictModel.objects.filter(key='foo3').exists(), True)
        self.assertEquals(ModelDictModel.objects.count(), base_count + 2)

        request_finished.send(sender=self)

        self.assertEquals(mydict._cache, None)

        # These should still error because even though the cache repopulates (local cache)
        # the remote cache pool does not
        # self.assertRaises(KeyError, mydict.__getitem__, 'foo3')
        # self.assertTrue(ModelDictModel.objects.filter(key='foo3').exists())
        # self.assertEquals(ModelDictModel.objects.count(), base_count + 2)

        self.assertEquals(mydict['foo'], 'bar2')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar2')
        self.assertEquals(ModelDictModel.objects.count(), base_count + 2)

        self.assertEquals(mydict.pop('foo'), 'bar2')
        self.assertEquals(mydict.pop('foo', None), None)
        self.assertFalse(ModelDictModel.objects.filter(key='foo').exists())
        self.assertEquals(ModelDictModel.objects.count(), base_count + 1)

    def test_modeldict_instances(self):
        base_count = ModelDictModel.objects.count()

        mydict = ModelDict(ModelDictModel, key='key', value='value', instances=True)
        mydict['foo'] = ModelDictModel(key='foo', value='bar')
        self.assertTrue(isinstance(mydict['foo'], ModelDictModel))
        self.assertTrue(mydict['foo'].pk)
        self.assertEquals(mydict['foo'].value, 'bar')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar')
        self.assertEquals(ModelDictModel.objects.count(), base_count + 1)
        old_pk = mydict['foo'].pk
        mydict['foo'] = ModelDictModel(key='foo', value='bar2')
        self.assertTrue(isinstance(mydict['foo'], ModelDictModel))
        self.assertEquals(mydict['foo'].pk, old_pk)
        self.assertEquals(mydict['foo'].value, 'bar2')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar2')
        self.assertEquals(ModelDictModel.objects.count(), base_count + 1)

        # test deletion
        mydict['foo'].delete()
        self.assertTrue('foo' not in mydict)

    def test_modeldict_expirey(self):
        base_count = ModelDictModel.objects.count()

        mydict = ModelDict(ModelDictModel, key='key', value='value')

        self.assertEquals(mydict._cache, None)

        mydict['test_modeldict_expirey'] = 'hello'

        self.assertEquals(len(mydict._cache), base_count + 1)
        self.assertEquals(mydict['test_modeldict_expirey'], 'hello')

        self.client.get('/')

        self.assertEquals(mydict._cache, None)
        self.assertEquals(mydict['test_modeldict_expirey'], 'hello')
        self.assertEquals(len(mydict._cache), base_count + 1)

        request_finished.send(sender=self)

        self.assertEquals(mydict._cache, None)
        self.assertEquals(mydict['test_modeldict_expirey'], 'hello')
        self.assertEquals(len(mydict._cache), base_count + 1)

    def test_modeldict_no_auto_create(self):
        # without auto_create
        mydict = ModelDict(ModelDictModel, key='key', value='value')
        self.assertRaises(KeyError, lambda x: x['hello'], mydict)
        self.assertEquals(ModelDictModel.objects.count(), 0)

    def test_modeldict_auto_create_no_value(self):
        # with auto_create and no value
        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        repr(mydict['hello'])
        self.assertEquals(ModelDictModel.objects.count(), 1)
        self.assertEquals(ModelDictModel.objects.get(key='hello').value, '')

    def test_modeldict_auto_create(self):
        # with auto_create and value
        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        mydict['hello'] = 'foo'
        self.assertEquals(ModelDictModel.objects.count(), 1)
        self.assertEquals(ModelDictModel.objects.get(key='hello').value, 'foo')

    def test_save_behavior(self):
        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        mydict['hello'] = 'foo'
        for n in xrange(10):
            mydict[str(n)] = 'foo'
        self.assertEquals(len(mydict), 11)
        self.assertEquals(ModelDictModel.objects.count(), 11)

        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        m = ModelDictModel.objects.get(key='hello')
        m.value = 'bar'
        m.save()

        self.assertEquals(ModelDictModel.objects.count(), 11)
        self.assertEquals(len(mydict), 11)
        self.assertEquals(mydict['hello'], 'bar')

        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        m = ModelDictModel.objects.get(key='hello')
        m.value = 'bar2'
        m.save()

        self.assertEquals(ModelDictModel.objects.count(), 11)
        self.assertEquals(len(mydict), 11)
        self.assertEquals(mydict['hello'], 'bar2')

    def test_django_signals_are_connected(self):
        from django.db.models.signals import post_save, post_delete
        from django.core.signals import request_finished

        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        self.assertHasReceiver(post_save, mydict._post_save)
        self.assertHasReceiver(post_delete, mydict._post_delete)
        self.assertHasReceiver(request_finished, mydict._cleanup)

    def test_celery_signals_are_connected(self):
        from celery.signals import task_postrun

        mydict = ModelDict(ModelDictModel, key='key', value='value', auto_create=True)
        self.assertHasReceiver(task_postrun, mydict._cleanup)


    # def test_modeldict_counts(self):
    #     # TODO:
    #     mydict = ModelDict(ModelDictModel, key='key', value='value')
    #     mydict['test_1'] = 'foo'
    #     mydict['test_2'] = 'bar'
    #     del mydict
    #     request_finished.send(sender=self)
    #
    #     mydict = ModelDict(ModelDictModel, key='key', value='value')
    #     # First and only cache.get() here.
    #     self.assertEqual(mydict['test_1'], 'foo')
    #     self.assertEqual(mydict['test_2'], 'bar')
    #     self.assertEqual(mydict['test_1'], 'foo')
    #
    #     request_finished.send(sender=self)
    #     # Should not be another cache.get().
    #     self.assertEqual(mydict['test_1'], 'foo')
    #     self.assertEqual(mydict['test_2'], 'bar')
    #     self.assertEqual(mydict['test_1'], 'foo')
    #
    #     self.assertEqual(cache._gets[c.get_key('ModelDict:ModelDictModel:key')], 1)
    #     self.assertEqual(cache._gets[c.get_key('ModelDict.last_updated:ModelDictModel:key')], 2)


class CachedDictTest(TestCase):
    @mock.patch('modeldict.base.CachedDict._update_cache_data')
    @mock.patch('modeldict.base.CachedDict.is_expired', mock.Mock(return_value=True))
    def test_expired_does_update_data(self, _update_cache_data):
        mydict = CachedDict()
        mydict._cache = {}
        mydict._last_updated = time.time()
        mydict._populate()

        _update_cache_data.assert_called_once_with()

    @mock.patch('modeldict.base.CachedDict._update_cache_data')
    @mock.patch('modeldict.base.CachedDict.is_expired', mock.Mock(return_value=False))
    def test_reset_does_expire(self, _update_cache_data):
        mydict = CachedDict(timeout=100)
        mydict._cache = {}
        mydict._last_updated = time.time()
        mydict._populate(reset=True)

        _update_cache_data.assert_called_once_with()

    @mock.patch('modeldict.base.CachedDict._update_cache_data')
    @mock.patch('modeldict.base.CachedDict.is_expired', mock.Mock(return_value=False))
    def test_does_not_expire_by_default(self, _update_cache_data):
        mydict = CachedDict(timeout=100)
        mydict._cache = {}
        mydict._last_updated = time.time()
        mydict._populate()

        self.assertFalse(_update_cache_data.called)
