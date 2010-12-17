----------------
django-modeldict
----------------

ModelDict is a very efficient way to store things like settings in your database. The entire model is transformed into a dictionary (lazily) as well as stored in your cache. It's invalidated only when it needs to be (both in process and based on ``CACHE_BACKEND``).

Quick example usage. More docs to come (maybe?)::


	class Setting(models.Model):
	    key = models.CharField(max_length=32)
	    value = models.CharField(max_length=200)
	settings = ModelDict(Setting, key='key', value='value', instances=False)
	
	# access missing value
	settings['foo']
	>>> KeyError
	
	# set the value
	settings['foo'] = 'hello'
	
	# fetch the current value using either method
	Setting.objects.get(key='foo').value
	>>> 'foo'
	
	settings['foo']
	>>> 'foo'