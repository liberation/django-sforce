from sforce.api.client import JsonResource

resources_tree = {
    'simple': {},
    'custom_path': {'path': 'custom/'},
    'custom_class': {'class': JsonResource},
    'custom_class_module': {'class': 'sforce.api.client.JsonResource'},
    'cascading': {'resources': {'foo':{}}},
}
