#!/usr/bin/env python

from setuptools import setup, find_packages

try:
    import multiprocessing
except:
    pass

tests_require = [
    'Django',
    'celery',
    'django-nose==1.0',
    'mock==0.8.0',
    'nose==1.1.2',
    'pyflakes',
    'pep8',
]

dependency_links = [
    'https://github.com/dcramer/pyflakes/tarball/master#egg=pyflakes',
]

setup(
    name='django-modeldict',
    version='1.3.0',
    author='DISQUS',
    author_email='opensource@disqus.com',
    url='http://github.com/disqus/django-modeldict/',
    description='Stores a model as a dictionary',
    packages=find_packages(),
    zip_safe=False,
    tests_require=tests_require,
    dependency_links=dependency_links,
    test_suite='runtests.runtests',
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)
