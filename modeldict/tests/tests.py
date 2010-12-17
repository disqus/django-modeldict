from django.core.cache import cache
from django.core.signals import request_finished
from django.test import TransactionTestCase

from modeldict import ModelDict
from modeldict.tests.models import ModelDictModel

class ModelDictTest(TransactionTestCase):
    # XXX: uses transaction test due to request_finished signal causing a rollback
    urls = 'modeldict.tests.urls'
    
    def test_api(self):
        base_count = ModelDictModel.objects.count()
        
        mydict = ModelDict(ModelDictModel, key='key', value='value')
        mydict['foo'] = 'bar'
        self.assertEquals(mydict['foo'], 'bar')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar')
        self.assertEquals(ModelDictModel.objects.count(), base_count+1)
        mydict['foo'] = 'bar2'
        self.assertEquals(mydict['foo'], 'bar2')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar2')
        self.assertEquals(ModelDictModel.objects.count(), base_count+1)
        mydict['foo2'] = 'bar'
        self.assertEquals(mydict['foo2'], 'bar')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo2'), 'bar')
        self.assertEquals(ModelDictModel.objects.count(), base_count+2)
        del mydict['foo2']
        self.assertRaises(KeyError, mydict.__getitem__, 'foo2')
        self.assertFalse(ModelDictModel.objects.filter(key='foo2').exists())
        self.assertEquals(ModelDictModel.objects.count(), base_count+1)
        
        ModelDictModel.objects.create(key='foo3', value='hello')

        self.assertEquals(mydict['foo3'], 'hello')
        self.assertTrue(ModelDictModel.objects.filter(key='foo3').exists(), True)
        self.assertEquals(ModelDictModel.objects.count(), base_count+2)
        
        request_finished.send(sender=self)
        
        self.assertEquals(mydict._cache, None)
        
        # These should still error because even though the cache repopulates (local cache)
        # the remote cache pool does not
        self.assertRaises(KeyError, mydict.__getitem__, 'foo3')
        self.assertTrue(ModelDictModel.objects.filter(key='foo3').exists())
        self.assertEquals(ModelDictModel.objects.count(), base_count+2)
        
        self.assertEquals(mydict['foo'], 'bar2')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar2')
        self.assertEquals(ModelDictModel.objects.count(), base_count+2)
        
        self.assertEquals(mydict.pop('foo'), 'bar2')
        self.assertEquals(mydict.pop('foo', None), None)
        self.assertFalse(ModelDictModel.objects.filter(key='foo').exists())
        self.assertEquals(ModelDictModel.objects.count(), base_count+1)
        
    def test_modeldict_instances(self):
        base_count = ModelDictModel.objects.count()
        
        mydict = ModelDict(ModelDictModel, key='key', value='value', instances=True)
        mydict['foo'] = ModelDictModel(key='foo', value='bar')
        self.assertTrue(isinstance(mydict['foo'], ModelDictModel))
        self.assertTrue(mydict['foo'].pk)
        self.assertEquals(mydict['foo'].value, 'bar')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar')
        self.assertEquals(ModelDictModel.objects.count(), base_count+1)
        old_pk = mydict['foo'].pk
        mydict['foo'] = ModelDictModel(key='foo', value='bar2')
        self.assertTrue(isinstance(mydict['foo'], ModelDictModel))
        self.assertEquals(mydict['foo'].pk, old_pk)
        self.assertEquals(mydict['foo'].value, 'bar2')
        self.assertEquals(ModelDictModel.objects.values_list('value', flat=True).get(key='foo'), 'bar2')
        self.assertEquals(ModelDictModel.objects.count(), base_count+1)

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