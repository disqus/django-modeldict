#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
    from setuptools.command.test import test
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages
    from setuptools.command.test import test

setup(
    name='django-modeldict',
    version='1.1.4',
    author='DISQUS',
    author_email='opensource@disqus.com',
    url='http://github.com/disqus/django-modeldict/',
    description = 'Stores a model as a dictionary',
    packages=find_packages(),
    zip_safe=False,
    tests_require=[
        'Django',
    ],
    test_suite = 'runtests.runtests',
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)