from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save

from sforce.api.client import JsonResource, ModelResource
from sforce.api.client import ModelBasedApi


class MyUser(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    api_id = models.CharField(max_length=32, null=True)


class MyUserResource(JsonResource, ModelResource):
    path = 'customer/'
    model = MyUser
    distant_id = 'api_id'
    fields_map = {'FirstName': 'first_name',
                  'LastName': 'last_name'}


class MyUserApi(ModelBasedApi):
    user_resources_tree = {'user': {'class': MyUserResource}}

    def __init__(self):
        self.resources_tree.update(self.user_resources_tree)
        super(MyUserApi, self).__init__()


@receiver(post_save, sender=MyUser)
def user_saved(sender, **kwargs):
    """
    Note: this is only an example,
    the api instance should probably be a global singleton
    and the api calls asynchronous
    """
    api = MyUserApi()
    api.push('user', sender)
