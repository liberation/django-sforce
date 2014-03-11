DJANGO-SFORCE
=============

Django-sforce is a Django client module for the SalesForce REST Api : http://www.salesforce.com/us/developer/docs/api_rest/.

It allows to easily access the whole api and synchronise with django models.

Why not [django-salesforce](https://github.com/freelancersunion/django-salesforce) ? As tempting as the custom DB backend approach looks like, I prefer a more straightforward client.


Basic Usage
-----------

```python
>>> from sforce.api import SalesForceApi
>>> api = SalesForceApi()
>>> api.get('Account')  # shortcut to api.get('sobjects.Account')
{...}
>>> api.post('Account', data={u'Name': u'foobar'})  # creates an Account
{i'id': i'001D000000IqhSLIAZ' ...}
>>> api.get('Account', params={u'id': '001D000000IqhSLIAZ'})  # get the created Account
{...}
>>> api.patch('Account', params={u'id': '001D000000IqhSLIAZ'}, data={'Name': 'barfoo'})  # updates the Account
{}
>>> from datetime import datetime, timedelta
>>> today = datetime.now()
>>> yesterday = today - timedelta(days=1)
>>> api.get('Account.updated', params={u'start': yesterday, u'end': today})  # fetch the updated Account(s)
{'ids': [u'001D000000IqhSLIAZ',], 'latestDateCovered': '_TODAY_'}
>>> api.delete('Account.instance', params={'id': u'001D000000IqhSLIAZ'})  # delete the Account
{}
>>> api.get('Account.deleted', params={u'start': yesterday,    # fetch deleted Account(s)
...                                    u'end': datetime.now()})
{u'deletedRecords': [{u'deletedDate': '_TODAY_', u'id': u'001D000000IqhSLIAZ'}], u'latestDateCovered': u'_TODAY_', u'earliestDateAvailable': u'_SOME_DATE_'}
```

When you instanciate the SalesForceApi, 3 things happen:  
* The resource tree is created, which means a class is created for every resources found in either ```api.resources_tree``` or the file pointed to by ```api.resources_tree_module```.
* The client authenticates itself with the API.
* The ```sobjects``` resource is fetched, and subsequent resources created dynamically.
You can then use the REST methods (head, get, post, patch, put or delete) to access the resources in ```api.resources```.
These methods all accepts 2 optional parameters:
  * ```params``` is a dictionary used to create the url in case it is dynamic, for example to specify the id, or the start/end dates for a DateRangeResource.
    The api does something like url.format(**params) to create the final url of the resource.
  * ```data``` is also a dictionary that contains the request body (mostly used by the post/patch methods), by default it will be formated to json.

In case you want to synchronise your models with the api, you can use ```ModelResource```, like this:  
```python
from django.db import models
from sforce.api.client import JsonResource, ModelResource
from sforce.api.client import ModelBasedApi


class MyUser(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    api_id = models.CharField(max_length=32, null=True)


class MyUserResource(JsonResource, ModelResource):
    path = 'Account/'
    model = MyUser
    distant_id = 'api_id'  # the name of the field storing the distant id
    fields_map = {'FirstName': 'first_name',  # a mapping between the distant and local field
                  'LastName': 'last_name'}


class MyUserApi(SalesForceApi):
    resources_tree = {'user': {'class': MyUserResource}}
```

Here we define a custom resource ```MyUserResource``` bound to the Django model ```MyUser``` via the ```api_id``` field.  
We also define a custom API that overrides completely the resources_tree class attribute, which means that the default salesforce resources won't be accessible.  
We can now do:  
```python
>>> api = MyUserApi()
>>> user = MyUser.objects.get(...)
>>> api.push('user', user)  # creates or updates the distant user depending on whether he has api_id set.
>>> api.pull('user', user)  # fetch the distant user and updates the local instance. 
```
The API will create the corresponding GET/POST/PATCH requests for you.  
You can pass ```save=False``` to ```api.pull``` in case you don't want to save the instance in db right away.  
A normal use case would be to call ```api.push``` in a ```post_save``` signal handler of the model, and ```api.pull``` in a cron fetching regularly ```user.updated``` and ```user.deleted```.  
Note that for now ```SalesForceApi``` do nothing if the distant object was deleted, it's you responsability to implement this logic.  


Settings
--------

* **SF_CONSUMER_KEY**  
  Mandatory
* **SF_CONSUMER_SECRET**  
  Mandatory 
* **SF_USER**
  Mandatory
* **SF_PASSWORD**
  Mandatory
* **SF_SECURITY_TOKEN**
  Only mandatory if server IP is not whitelisted in the salesforce admin
* **SF_API_VERSION** = '29.0'
  Because I don't test the api directly, I can't promise the older versions of the api would work.  
  But the newer versions definitively should.
* **SF_AUTH_DOMAIN** = 'https://test.salesforce.com/'  
  Change this to 'https://login.salesforce.com/' in a production environement.
* **SF_SOBJECTS_WHITELIST** = []  
  If not empty, will only populate sobjects resources from this list.  
  It allows to avoid the overhead from non used salesforce objects and keep the resource list clean.  


Advanced Usage
--------------

* Logger
* Create a custom resource
* Create a custom api, extends the default api resources
* Use the xml format

TODO
----

* Advanced usage docs
* Special resources Query and Search
* Django 1.5 & 1.6
