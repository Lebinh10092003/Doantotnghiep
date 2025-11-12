import json
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.filter
def json_to_query_string(value):
    """
    Converts a dictionary or a JSON string into a URL query string.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return ""
    if isinstance(value, dict):
        return urlencode(value)
    return ""

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