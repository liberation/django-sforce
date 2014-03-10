"""
Note: list of error codes i bumped into, we might want to recover from some of them
+ INVALID_SESSION_ID
+ ENTITY_IS_DELETED
+ NOT_FOUND
+ INVALID_FIELD_FOR_INSERT_UPDATE
+ INVALID_DATE_FORMAT

usage:
> from sforce.api import SalesForceApi
> api = SalesForceApi()
> api.get('recent')
> {...}
> api.get('Account')  # shortcut to api.get('resources_list.Account')
> {...}  # describe the Account object
> api.post('Account', data={u'Name': u'foobar'})  # create an Account
> {i'id': i'001D000000IqhSLIAZ' ...}
> api.get('Account.instance', params={u'id': '001D000000IqhSLIAZ'})
> {...}  # get all fields values
> api.patch('Account.instance', params={u'id': '001D000000IqhSLIAZ'}, data={'Name': 'barfoo'})  # update the Account
> {}
> today = datetime.now()
> yesterday = today - timedelta(days=1)
> api.get('Account.updated', params={u'start': yesterday, u'end': today})
> {'ids': [u'001D000000IqhSLIAZ',], 'latestDateCovered': '_TODAY_'}
> api.delete('Account.instance', params={'id': u'001D000000IqhSLIAZ'})
> {}
> api.get('Account.deleted', params={u'start': yesterday, u'end': today})
> {u'deletedRecords': [{u'deletedDate': '_TODAY_', u'id': u'001D000000IqhSLIAZ'}], u'latestDateCovered': u'_TODAY_', u'earliestDateAvailable': u'_SOME_DATE_'}
"""

import urlparse

try:
    from django.conf import settings
except ImportError:
    from sforce import settings
from django.utils import simplejson as json

from requests_oauthlib.oauth2_session import OAuth2Session
from oauthlib.oauth2 import LegacyApplicationClient
from oauthlib.oauth2.rfc6749.parameters import validate_token_parameters

from .client import RestApi
from .client import JsonResource
from .client import InstanceResource
from .client import ModelBasedApi
from .client import DateRangeResource
from .client import ExternalIdInstanceResource

from logging import getLogger
log = getLogger(__package__)


class SalesForceLegacyApplicationClient(LegacyApplicationClient):
    """
    we need to override oauth2.LegacyApplicationClient,
    because sales force does not comply entirely to the oauth rfc
    also, we need to know the instance_url returned
    """

    def parse_request_body_response(self, body, scope=None):
        token = json.loads(body)
        token['token_type'] = self.token_type
        validate_token_parameters(token, scope)
        # TODO: use token['signature'] to make sure the the request was not compromized
        self._populate_attributes(token)
        self.token = token
        return self.token


class SalesForceAuthApi(RestApi):
    """
    Uses requests.oauth1_session to authentify etc
    requires: requests_oauthlib
    """
    error_key = 'errorCode'
    auth_error = 'INVALID_SESSION_ID'

    token_request_url = '%s/services/oauth2/token' % settings.SF_AUTH_DOMAIN
    username = settings.SF_USER
    password = settings.SF_PASSWORD + settings.SF_SECURITY_TOKEN
    client_key = settings.SF_CONSUMER_KEY
    client_secret = settings.SF_CONSUMER_SECRET

    def __init__(self):
        super(SalesForceAuthApi, self).__init__()
        self.get_session_id()

    def _get_session(self):
        return OAuth2Session(client=SalesForceLegacyApplicationClient(client_id=self.client_key))

    def get_session_id(self):
        token = self.session.fetch_token(self.token_request_url,
                                         username=self.username,
                                         password=self.password,
                                         client_id=self.client_key,
                                         client_secret=self.client_secret)
        log.info('Fetched token %s' % token)
        self.domain = token['instance_url']

    def _dispatch(self, *args, **kwargs):
        rerun = kwargs.pop('rerun', None)
        response = super(SalesForceAuthApi, self)._dispatch(*args, **kwargs)
        if response and self.error_key in response:
            # we had an Authentification exception
            # trying to refetch a token and rerun the request
            if response[self.error_key] == self.auth_error and not rerun:
                log.warning('Got %s error, trying to fetch another token and rerun the request.' % self.auth_error)
                self.get_session_id()
                kwargs['rerun'] = True  # ensure we will not try to do it indefinitely
                self._dispatch(*args, **kwargs)
        return response


class SalesForceResource(JsonResource):
    error_key = u'errorCode'
    methods = ['GET']


class DeletedResource(SalesForceResource, DateRangeResource):
    path = 'deleted/?start={start}&end={end}'


class UpdatedResource(SalesForceResource, DateRangeResource):
    path = 'updated/?start={start}&end={end}'


class SFInstanceResource(SalesForceResource, InstanceResource):
    pass


class SFExternalIdInstanceResource(SalesForceResource, ExternalIdInstanceResource):
    pass


class QueryResource(SalesForceResource):
    pass


class QueryAllResource(QueryResource):
    pass


class SearchResource(QueryResource):
    pass


class SObjectResource(SalesForceResource):
    """
    'super' resource handling /Foo/ AND /Foo/instance
    """
    methods = ['GET', 'POST', 'PATCH', 'DELETE']


class SObjectsResource(SalesForceResource):
    sobjects_whitelist = getattr(settings, 'SF_SOBJECTS_WHITELIST', None) or {}

    def post_process(self, method, data):
        # we populate the resources
        if self.sobjects_whitelist:
            sobjects = [d for d in data['sobjects'] if d['name'] in self.sobjects_whitelist]
        else:
            sobjects = data['sobjects']

        for obj in sobjects:
            name = obj['name']
            resources = dict([(r, {}) for r in obj['urls']])
            self.api.make_resource(name,
                                   {'class': 'sforce.api.salesforce.SObjectResource',
                                    'resources': resources},
                                   parent=self)


class SalesForceApi(ModelBasedApi, SalesForceAuthApi):  # CachedApi
    base_resource_class = SalesForceResource
    scheme = 'https'  # not actualy used, only here for information
    timeout = 2  # TODO: the sandbox is sloww...
    root_path = u'services/data/v%s/' % settings.SF_API_VERSION
    cache_prefix = 'SalesForceApi'
    resources_tree_module = settings.SF_RESOURCES

    def __init__(self):
        super(SalesForceApi, self).__init__()
        self.get('sobjects')

    def get_resource(self, resource_name, **kwargs):
        """
        proxy sobjects.Foo to Foo for convenience
        """
        proxy = 'sobjects.%s' % resource_name
        if not resource_name.startswith('sobjects.') and proxy in self.resources:
            resource_name = proxy
        return super(SalesForceApi, self).get_resource(resource_name, **kwargs)

    def get_base_url(self):
        """
        Overrides get_base_url because the scheme is included in the domain
        (returned by the token fetching request)
        """
        return urlparse.urljoin(self.domain, self.root_path)
