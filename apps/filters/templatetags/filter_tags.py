from django import template
from apps.filters.utils import serialize_query_params

register = template.Library()

@register.filter
def json_to_query_string(value):
    """
    Converts a dictionary or a JSON string into a URL query string.
    """
    return serialize_query_params(value)

@register.simple_tag(takes_context=True)
def remove_query_param(context, key_to_remove):
    """
    Removes a specific key from the current request's GET parameters and returns the new query string.
    """
    query_dict = context['request'].GET.copy()
    if key_to_remove in query_dict:
        query_dict.pop(key_to_remove)
    
    # Ensure 'page' is removed to reset pagination when a filter changes
    if 'page' in query_dict:
        query_dict.pop('page')
        
    return query_dict.urlencode()