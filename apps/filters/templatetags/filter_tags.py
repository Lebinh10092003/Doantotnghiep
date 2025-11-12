import json
from django import template
from django.utils.http import urlencode

register = template.Library()

@register.filter
def json_to_query_string(json_string):
    """Converts a JSON string of a dictionary to a URL query string."""
    try:
        params = json.loads(json_string)
        return urlencode(params, doseq=True)
    except (json.JSONDecodeError, TypeError):
        return ""
