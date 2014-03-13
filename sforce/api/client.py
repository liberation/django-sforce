import urllib
import urlparse
import requests
from datetime import datetime

from logging import getLogger

log = getLogger(__package__)


class APIException(Exception):
    pass


class BaseResource(object):
    """
    An abstract class for any REST api resource.
    """
    path = ''
    methods = ['HEAD', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    error_key = 'error'
    timeout = 1  # in seconds

    def __init__(self, api, **kwargs):
        self.api = api
        # url parameters
        self.params = kwargs.get('params', {})
        self.parent = kwargs.get('parent', None)

    def get_path(self):
        return self.path.format(**dict(zip(self.params, map(urllib.quote, self.params.values()))))

    def get_url(self):
        """
        Construct the full url from the Api scheme, domain and the resource path.
        """
        return urlparse.urljoin(self.api.get_base_url(), self.get_path())

    def get_headers(self):
        return {}

    def format_data(self, data):
        return str(data)

    def parse_response(self, response):
        return response.text

    def _request(self,
                 method,
                 data={},        # content data
                 ok_code=requests.codes[u'\o/'],  # == 200
                 **kwargs):
        """
        Either returns a dict or raise an APIException
        """
        if not method in self.methods:
            raise ValueError(u"The method %s is not available for the resource %s." % (method, self))
        url = self.get_url()
        try:
            log.info(u'Accessing api %s : %s -data- %s' % (method, url, data))
            response = self.api.session.request(method,
                                                url,
                                                data=self.format_data(data),
                                                headers=self.get_headers(),
                                                timeout=self.timeout)
        except requests.Timeout:
            msg = u'Api call on %s : %s timed out !' % (method, url)
            log.error(msg)
            raise APIException(msg)

        log.debug('Api call returned : %s', response.text)
        if ok_code != requests.codes.no_content:
            payload = self.parse_response(response)
        else:
            # Some methods expect an empty response : PUT, PATCH and DELETE
            payload = {}  # TODO: TBD: should we return None ?

        if response.status_code != ok_code:
            msg = u'Api call on %s : %s returned a status code %s, expected a %s.' % (method, url, response.status_code, ok_code)
            if type(payload) == list:
                payload = payload[0]  # Note: i don't like that
            if self.error_key in payload:
                msg += ' : %s' % payload
            log.error(msg)
            raise APIException(msg)

        self.post_process(method, payload)
        return payload

    def head(self, data={}):
        self._request('HEAD', data)

    def get(self, data={}):
        return self._request('GET', data)

    def post(self, data):
        return self._request('POST', data, ok_code=requests.codes.created)

    def put(self, data):
        return self._request('PUT', data, ok_code=requests.codes.no_content)

    def patch(self, data):
        return self._request('PATCH', data, ok_code=requests.codes.no_content)

    def delete(self, data={}):
        return self._request('DELETE', data, ok_code=requests.codes.no_content)

    def post_process(self, method, data):
        pass


class RestApi(object):
    """
    An abstract class for a REST Api client.
    """
    scheme = 'http'
    domain = 'over.ride.me'
    root_path = 'api/vX.X/'

    sub_resource_separator = '.'
    base_resource_class = BaseResource
    resources_tree = None
    resources_tree_module = ''

    def __init__(self):
        self.session = self._get_session()
        self.resources = {}
        self.build_api()

    def raw(self, method, path, data={}):
        """
        Performs a raw request on the api, using the default resource class
        mostly for testing and exploration purposes
        """
        res = self.base_resource_class(self)
        res.path = path
        response = getattr(res, method.lower())(data)
        del res
        return response

    def make_resource(self, name, node, parent=None):
        cls = node.get('class') or self.base_resource_class
        if isinstance(cls, (str, unicode)):
            module, cls_name = cls.rsplit('.', 1)
            # TODO: use importlib
            m = __import__(module, globals(), locals(), [cls_name], -1)
            cls = getattr(m, cls_name)

        path = node.get('path') or getattr(cls, 'path', None) or '%s/' % name
        if parent:
            name = '%s%s%s' % (parent.name,
                               self.sub_resource_separator,
                               name)
            path = '%s%s' % (parent.path, path)

        new_cls = type('_%sResource' % name.encode('ascii', errors='ignore').replace('.', ''),
                       (cls,), {'name': name,
                                'path': path})
        self.resources[name] = new_cls
        subnodes = node.get('resources')
        if subnodes:
            for name, snode in subnodes.iteritems():
                self.make_resource(name, snode, parent=new_cls)

    def build_api(self):
        """
        Creates all resources implicitly declared
        """
        if not self.resources_tree and not self.resources_tree_module:
            raise AttributeError("Either resources_tree or resources_tree_module must be set.")
        elif not self.resources_tree and self.resources_tree_module:
            m = __import__(self.resources_tree_module,
                           globals(), locals(), ['resources_tree'], -1)
            self.resources_tree = m.resources_tree

        for name, node in self.resources_tree.iteritems():
            self.make_resource(name, node)

    def get_base_url(self):
        return urlparse.urljoin('%s://%s' % (self.scheme, self.domain),
                                self.root_path)

    def _get_session(self):
        return requests.Session()

    def get_resource(self, resource, **kwargs):
        if isinstance(resource, BaseResource):
            return resource

        if not resource in self.resources:
            raise APIException("%s is not a valid resource." % resource)
        return self.resources[resource](self, **kwargs)

    def _dispatch(self, resource, method, params={}, data={}):
        resource = self.get_resource(resource, params=params)
        return getattr(resource, method.lower())(data)

    def head(self, resource, params={}, data={}):
        return self._dispatch(resource, 'HEAD', params, data)

    def get(self, resource, params={}, data={}):
        return self._dispatch(resource, 'GET', params, data)

    def post(self, resource, params={}, data={}):
        return self._dispatch(resource, 'POST', params, data)

    def put(self, resource, params={}, data={}):
        return self._dispatch(resource, 'PUT', params, data)

    def patch(self, resource, params={}, data={}):
        return self._dispatch(resource, 'PATCH', params, data)

    def delete(self, resource, params={}, data={}):
        return self._dispatch(resource, 'DELETE', params, data)


class JsonResource(BaseResource):
    def get_headers(self):
        return {"Content-Type": "application/json"}

    def parse_response(self, response):
        try:
            return response.json()
        except ValueError, e:
            msg = u'Api call on returned invalid json : %s !' % (response.text)
            log.error(msg + e.message)
            raise APIException(msg)


class DateRangeResource(BaseResource):
    """
    Convenience class for a resource that needs which is comprised between 2 dates
    """
    # TODO: use non naive datetime objects
    # TODO: add a 'since' convenience parameter ?!
    date_start_param = 'start'
    date_end_param = 'end'
    date_format = "%Y-%m-%dT%H:%M:%S+00:00"

    def get_path(self):
        try:
            if self.params['start'] >= self.params['end']:
                raise ValueError(u"The 'start' parameter must chronologically precede 'end'.")
            self.params[self.date_start_param] = datetime.strftime(self.params[self.date_start_param], self.date_format)
            self.params[self.date_end_param] = datetime.strftime(self.params[self.date_end_param], self.date_format)
        except KeyError:
            raise ValueError(u"'%s' and '%s' are both mandatory parameters for the %s resource." % (self.date_start_param, self.date_end_param, self.__class__))
        except TypeError:
            raise TypeError(u"'%s' and '%s' parameters for the %s resource should be instances of datetime.datetime." % (self.date_start_param, self.date_end_param, self.__class__))
        return super(DateRangeResource, self).get_path()


class InstanceResource(BaseResource):
    """
    Convenience class for a resource describing a single object identified by it's id
    """
    path = '{id}/'
    methods = ['HEAD', 'GET', 'PATCH', 'DELETE']

    def get_path(self):
        if not u'id' in self.params:
            raise ValueError(u"'id' is a mandatory parameter of an %s." % self.__class__.__name__)
        return super(InstanceResource, self).get_path()


class ExternalIdInstanceResource(BaseResource):
    """
    Convenience class for a resource describing a single object
    identified by an external id to the API, probably YOUR id.
    """
    path = '{fieldname}/{fieldvalue}/'
    methods = ['HEAD', 'GET', 'PATCH', 'DELETE']

    def get_path(self):
        if not u'fieldname' in self.params or not u'fieldvalue' in self.params:
            raise ValueError(u"'fieldname' and 'fieldvalue' are both mandatory parameters of an %s." % self.__class__.__name__)
        return super(ExternalIdInstanceResource, self).get_path()


### django specific
class ModelResource(BaseResource):
    """
    Map a resource to a django model
    Note: the default behavior is to add {id}/ to the path when resource.instance is specified.
    If the id is specified in another way (in the get parameters for exp: ?id=foo), you need to override get_path.
    """
    model = None
    distant_id = 'dist_id'  # local name of the distant id
    fields_map = {}

    def __init__(self, api, **kwargs):
        super(ModelResource, self).__init__(api, **kwargs)
        self.instance = kwargs.get('instance', None)

    def get_path(self):
        if 'id' not in self.params and getattr(self.instance, self.distant_id, None):
            self.params['id'] = getattr(self.instance, self.distant_id)
            self.path += '{id}/'
        return super(ModelResource, self).get_path()

    def get_local_value(self, distant_field, distant_value):
        """
        From the distant value to the local value
        exp: 'France' becomes 1
        """
        method_name = 'get_local_%s_value' % distant_field
        if hasattr(self, method_name):
            return getattr(self, method_name)(distant_value)
        else:
            return distant_value

    def get_distant_value(self, distant_field, local_value):
        """
        From the local value to the distant value
        exp: 1 would become 'France'
        """
        method_name = 'get_local_%s_value' % distant_field
        if hasattr(self, method_name):
            return getattr(self, method_name)(local_value)
        else:
            return local_value

    def get_fields(self):
        return self.fields_map


class ModelBasedApi(RestApi):
    """
    Convenience class using ModelInstanceResource(s) alowing to do
    > u = User.objects.get(email=x)
    > api = MyApi()
    > api.pull('Account', u)  # synchro distant -> local
    > u.first_name = 'fooo'
    > u.save()
    >
    > u.last_name = 'bar'
    > api.push('Account', u)  # synchro local -> distant
    """

    def pull(self, resource_name, instance, save=True):
        resource = self.get_resource(resource_name, instance=instance)

        dist_id = getattr(instance, resource.distant_id, None)
        if not dist_id:
            raise ValueError('%s(%s) has no %s ! You can not pull it !' % (instance, instance.__class__, resource.distant_id))

        payload = self.get(resource)
        for distant, local in resource.get_fields().iteritems():
            setattr(instance, local, resource.get_local_value(distant, payload[distant]))
        if save:
            instance.save()
        return payload

    def push(self, resource_name, instance):
        resource = self.get_resource(resource_name, instance=instance)

        fields = dict([(k, resource.get_distant_value(k, getattr(instance, v))) for k, v in resource.get_fields().iteritems()])

        if getattr(instance, resource.distant_id, None):
            # update - TODO: check the updated fields returned ?
            return self.patch(resource, data=fields)
        else:
            # create
            payload = self.post(resource, data=fields)
            # if no exception was raised, it's a success
            setattr(instance, resource.distant_id, payload['id'])
            instance.save()
            return payload
