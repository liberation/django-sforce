"""Setup script of django-sforce"""
from setuptools import setup
from setuptools import find_packages

import sforce

setup(
    name='django-sforce',
    version=sforce.__version__,

    description='Django-sforce is a Django client module for the SalesForce REST Api',
    long_description=[open('README').read(),],
    keywords='django, salesforce, crm, api, rest',

    author=sforce.__author__,
    author_email=sforce.__email__,
    url=sforce.__url__,

    packages=find_packages(exclude=['testproject',]),
    classifiers=[
        'Framework :: Django',
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Programming Language :: Python',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: BSD License',
        'Topic :: Software Development :: Libraries :: Python Modules'],

    license=sforce.__license__,
    zip_safe=False,
    install_requires=['requests',
                      'oauthlib',
                      'requests_oauthlib']
)
