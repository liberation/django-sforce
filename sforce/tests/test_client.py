import mock
import json
import requests
from requests_oauthlib import OAuth2Session

from django.test import TestCase
from django.db.models.signals import post_save

from sforce.api.client import APIException
from sforce.api.client import RestApi
from sforce.api.client import BaseResource, JsonResource
from sforce.api.salesforce import SalesForceApi

from testproject.testapp.models import MyUser, MyUserApi, user_saved


class MockResponse(object):
    def __init__(self, api):
        self.api = api
        self.headers = {}

    def json(self):
        return json.loads(self.text)

    @property
    def text(self):
        return self.api.return_value

    @property
    def status_code(self):
        return self.api.status_code


class TestApi(RestApi):
    scheme = 'https'
    domain = 'api.test.com'
    root_path = 'rest/v1.0/'

    resources_tree = {'simple': {},
                      'custom_path': {'path': 'custom/'},
                      'custom_class': {'class': JsonResource},
                      'custom_class_module': {'class': 'sforce.api.client.JsonResource'},
                      'cascading': {'resources': {'foo':{}}},
                      }

    def __init__(self):
        # only set it if not already set
        self.return_value = getattr(self, 'return_value', '{"success": true}')
        self.status_code = requests.status_codes.codes.ok
        super(TestApi, self).__init__()

    def _get_session(self):
        session = super(TestApi, self)._get_session()
        session.request = mock.MagicMock(return_value=MockResponse(self))
        return session


class BaseResourceTest(TestCase):
    def setUp(self):
        self.api = TestApi()
        self.resource = BaseResource(self.api)

    def test_invalid_method(self):
        self.resource.methods = ['HEAD']
        with self.assertRaises(ValueError):
            self.resource.get()

    def test_invalid_path_params(self):
        self.resource.path = '{foo}/'
        with self.assertRaises(KeyError):
            self.resource.get()

        self.resource.path = 'bar/'
        self.resource.get()

    def test_path(self):
        self.resource.path = '{foo}/'
        self.resource.params = {'foo': 'bar'}
        path = self.resource.get_path()
        self.assertEqual(path, 'bar/')

    def test_post_process_is_called(self):
        with mock.patch.object(self.resource, 'post_process', return_value=None) as pp:
            self.resource.get()
        pp.assert_called_once()


class JsonResourceTest(TestCase):
    def setUp(self):
        self.api = TestApi()

    def test_parse_response(self):
        response = self.api.get('custom_class')
        self.assertEqual(response, {"success": True})

    def test_invalid_response(self):
        self.api.return_value = "{'invalid': json]}"
        with self.assertRaises(APIException):
            self.api.get('custom_class')


class DateRangeResourceTest(TestCase):
    pass


class InstanceResourceTest(TestCase):
    pass


class ExternalIdInstanceResourceTest(TestCase):
    pass


class RestApiTest(TestCase):
    def setUp(self):
        self.api = TestApi()

    def test_session_obj(self):
        self.assertTrue(isinstance(self.api.session, requests.Session))

    def _check_resource(self, api, resource_name, name=None, path=None, cls=None):
        r = api.get_resource(resource_name)
        self.assertEqual(r.name, name)
        self.assertEqual(r.__class__.__name__, ('_%sResource' % r.name).replace('.', ''))
        self.assertEqual(r.path, path)
        self.assertTrue(isinstance(r, cls))

    def _test_resources(self, api):
        """
        {'simple': {},
        'custom_path': {'path': 'custom/'},
        'custom_class': {'class': JsonResource},
        'custom_class_module': {'class': 'sforce.api.client.JsonResource'},
        'cascading': {'resources': {'foo':{}}},
        }
        """
        self._check_resource(api, 'simple',
                             name='simple',
                             path='simple/',
                             cls=BaseResource)
        self._check_resource(api, 'custom_path',
                             name='custom_path',
                             path='custom/',
                             cls=BaseResource)
        self._check_resource(api, 'custom_class',
                             name='custom_class',
                             path='custom_class/',
                             cls=JsonResource)
        self._check_resource(api, 'custom_class_module',
                             name='custom_class_module',
                             path='custom_class_module/',
                             cls=JsonResource)
        self._check_resource(api, 'cascading',
                             name='cascading',
                             path='cascading/',
                             cls=BaseResource)
        self._check_resource(api, 'cascading.foo',
                             name='cascading.foo',
                             path='cascading/foo/',
                             cls=BaseResource)

    def test_no_resource_tree(self):
        MyApi = type('MyApi', (TestApi,), {'resources_tree': None})
        with self.assertRaises(AttributeError):
            MyApi()

    def test_load_resources_tree(self):
        api = TestApi()
        self._test_resources(api)

    def test_load_resources_tree_module(self):
        # if self.resources_tree or self.resources_tree_module is set
        MyApi = type('MyApi', (TestApi,), {'resources_tree': None,
                                           'resources_tree_module': 'sforce.tests.test_resources'})
        api = MyApi()
        self._test_resources(api)

    def test_invalid_resource(self):
        with self.assertRaises(APIException):
            self.api.get_resource('foobar')
        # foo alone won't work, need cascading.foo
        with self.assertRaises(APIException):
            self.api.get_resource('foo')
        self.api.get_resource('cascading.foo')

    def test_base_url(self):
        self.assertEqual(self.api.get_base_url(), u'https://api.test.com/rest/v1.0/')

    def _test_request(self, resource_name, method, data=None, status_code=200):
        self.api.status_code = status_code
        resource = self.api.get_resource(resource_name)
        self.api.session.request = mock.MagicMock(return_value=MockResponse(self.api))

        getattr(resource, method.lower())(data)  # api call
        self.api.session.request.assert_called_once_with(method,
                                                         resource.get_url(),
                                                         headers=resource.get_headers(),
                                                         data=data,
                                                         timeout=resource.timeout)

    def test_head(self):
        self._test_request('simple', 'HEAD')

    def test_get(self):
        self._test_request('simple', 'GET')

    def test_post(self):
        self._test_request('simple', 'POST', {}, status_code=requests.status_codes.codes.created)

    def test_put(self):
        self._test_request('simple', 'PUT', {}, status_code=requests.status_codes.codes.no_content)

    def test_patch(self):
        self._test_request('simple', 'PATCH', {}, status_code=requests.status_codes.codes.no_content)

    def test_delete(self):
        self._test_request('simple', 'DELETE', status_code=requests.status_codes.codes.no_content)


class MyUserTestApi(TestApi, MyUserApi):
    pass


class ModelSyncTest(TestCase):
    """
    Django specific
    """
    def setUp(self):
        # disconnecting signal to use the mocked api
        post_save.disconnect(user_saved, sender=MyUser)
        self.user = MyUser.objects.create(first_name='foo', last_name='bar')
        self.api = MyUserTestApi()

    def test_url_params(self):
        # should contain id if instance is set
        pass

    def test_create(self):
        self.api.status_code = requests.status_codes.codes.created
        self.api.return_value = u'{"id" : "001D000000IqhSLIAZ", "errors" : [], "success" : true}'

        self.api.push('user', self.user)
        self.api.session.request.assert_called_once_with('POST',
                                                         'https://api.test.com/rest/v1.0/customer/',
                                                         headers={'Content-Type': 'application/json'},
                                                         data={"LastName": "bar", "FirstName": "foo"},
                                                         timeout=1)
        self.assertEqual(self.user.api_id, "001D000000IqhSLIAZ")

    def test_update(self):
        # push - update - returns the updated fields
        self.user.api_id = '001D000000IqhSLIAZ'
        self.user.first_name = 'foo2'
        self.user.save()

        self.api.status_code = requests.status_codes.codes.no_content
        self.api.return_value = u'{"FirstName" : "foo2"}'

        self.api.push('user', self.user)
        self.api.session.request.assert_called_once_with('PATCH',
                                                         'https://api.test.com/rest/v1.0/customer/001D000000IqhSLIAZ/',
                                                         headers={'Content-Type': 'application/json'},
                                                         data={"LastName": "bar", "FirstName": "foo2"},
                                                         timeout=1)

    def test_fetch(self):
        self.user.api_id = '001D000000IqhSLIAZ'
        self.user.save()

        self.api.return_value = u'{"LastName": "bar3", "FirstName": "foo3"}'
        self.api.pull('user', self.user)
        self.api.session.request.assert_called_once_with('GET',
                                                         'https://api.test.com/rest/v1.0/customer/001D000000IqhSLIAZ/',
                                                         headers={'Content-Type': 'application/json'},
                                                         data={},
                                                         timeout=1)
        self.assertEqual(self.user.first_name, 'foo3')
        self.assertEqual(self.user.last_name, 'bar3')

    def test_fetch_unsynced(self):
        with self.assertRaises(ValueError):
            self.api.pull('user', self.user)


class MySalesForceApi(TestApi, SalesForceApi):
    """
    Sales Force specific
    """
    def __init__(self, *args, **kwargs):
        # need to set the return value before the call to sobjects
        # Note: the Contact object shouldn't be 'resourcified' because not specified in settings.SF_SOBJECTS_WHITELIST
        self.return_value = u'{"encoding":"UTF-8", "sobjects": [{"name":"Account","label":"Account","customSetting":false,"undeletable":true,"mergeable":true,"replicateable":true,"triggerable":true,"feedEnabled":false,"retrieveable":true,"deprecatedAndHidden":false,"custom":false,"keyPrefix":"001","layoutable":true,"activateable":false,"labelPlural":"Accounts","urls":{"sobject":"/services/data/v29.0/sobjects/Account","quickActions":"/services/data/v29.0/sobjects/Account/quickActions","describe":"/services/data/v29.0/sobjects/Account/describe","rowTemplate":"/services/data/v29.0/sobjects/Account/{ID}","layouts":"/services/data/v29.0/sobjects/Account/describe/layouts","compactLayouts":"/services/data/v29.0/sobjects/Account/describe/compactLayouts"},"searchable":true,"queryable":true,"createable":true,"deletable":true,"updateable":true}, {"name":"Contact","label":"Contact","customSetting":false,"undeletable":true,"mergeable":true,"replicateable":true,"triggerable":true,"feedEnabled":false,"retrieveable":true,"deprecatedAndHidden":false,"custom":false,"keyPrefix":"002","layoutable":true,"activateable":false,"labelPlural":"Contacts","urls":{"sobject":"/services/data/v29.0/sobjects/Contact","quickActions":"/services/data/v29.0/sobjects/Contact/quickActions","describe":"/services/data/v29.0/sobjects/Contact/describe","rowTemplate":"/services/data/v29.0/sobjects/Contact/{ID}","layouts":"/services/data/v29.0/sobjects/Contact/describe/layouts","compactLayouts":"/services/data/v29.0/sobjects/Contact/describe/compactLayouts"},"searchable":true,"queryable":true,"createable":true,"deletable":true,"updateable":true}]}'

        # empty the test resource tree because we want to load saleforce's
        self.resources_tree = None
        super(MySalesForceApi, self).__init__(*args, **kwargs)
        # then use default return_value again
        self.return_value = u'{"success": true}'


class SalesForceApiTest(TestCase):
    """
    SalesForce specific logic
    """
    def __init__(self, *args, **kwargs):
        # Note: using init instead of setUp because i only want this done once.
        super(SalesForceApiTest, self).__init__(*args, **kwargs)

        self.token_response = {u'access_token': u'ACCESS_TOKEN', u'token_type': u'Bearer', u'signature': u'SIGNATURE', u'issued_at': u'1392809231037', u'instance_url': u'https://footest.salesforce.com', u'id': u'https://footest.salesforce.com/id/00D11000000CqsdEAC/005b0000000vDaGAAU'}

        with mock.patch.object(OAuth2Session, 'fetch_token', return_value=self.token_response) as mock_fetch_token:
            self.api = MySalesForceApi()
        self.mock_fetch_token = mock_fetch_token

    def test_api_init(self):
        self.mock_fetch_token.assert_called_once()
        self.api.session.request.assert_called_once_with('GET',
                                                         'https://footest.salesforce.com/rest/v1.0/sobjects/',
                                                         headers={'Content-Type': 'application/json'},
                                                         data={},
                                                         timeout=1)

    def test_resources_list_proxy(self):
        # if this is loaded and proxied, it won't raise a ValueError
        self.api.get_resource('Account')
        self.api.get_resource('sobjects.Account')
        with self.assertRaises(APIException):
            self.api.get_resource('Account_fooo')

    def test_cascading_resource_path(self):
        expected = 'sobjects/Account/'
        r = self.api.get_resource('Account')
        self.assertEqual(r.get_path(), expected)

    def test_sobjects_whitelist(self):
        # not loaded because not in settings.SF_SOBJECTS_WHITELIST
        with self.assertRaises(APIException):
            self.api.get_resource('Contact')

    def test_invalid_session_id_recover(self):
        self.api.get('recent')  # call with a fresh token
        self.mock_fetch_token.assert_not_called()
        self.api.return_value = u'{"errorCode":"INVALID_SESSION_ID", "msg":"Session expired or invalid"}'
        with mock.patch.object(OAuth2Session, 'fetch_token', return_value=self.token_response) as mock_fetch_token:
            self.api.get('recent')

        # 1 for sobjects
        # 2 for first 'recent' get
        # 3 for invalid token
        # 4 for rerun
        self.assertEqual(self.api.session.request.call_count, 4)
        mock_fetch_token.assert_called_once()
