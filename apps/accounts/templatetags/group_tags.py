# apps/accounts/templatetags/group_tags.py
from django import template

register = template.Library()

# DANH SÁCH NHÓM ĐƯỢC BẢO VỆ (phải khớp với danh sách trong views.py)
PROTECTED_GROUPS = [
    'Admin', 
    'Teacher', 
    'Student', 
    'Parent', 
    'Center Manager', 
    'Assistant',
    'Staff' 
]

@register.filter
def is_protected_group(group_name):
    """Kiểm tra xem tên nhóm có nằm trong danh sách được bảo vệ không."""
    if not group_name:
        return False
    return group_name in PROTECTED_GROUPS

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