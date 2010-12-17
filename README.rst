----------------
django-modeldict
----------------

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