# apps/accounts/templatetags/group_tags.py
from django import template

register = template.Library()

@register.filter
def in_group(user, group_name):
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        return user.groups.filter(name=group_name).exists()
    except Exception:
        return False

@register.filter
def in_any_group(user, group_names):
    if not getattr(user, "is_authenticated", False):
        return False
    names = [g.strip() for g in group_names.split(",")]
    return user.groups.filter(name__in=names).exists()
