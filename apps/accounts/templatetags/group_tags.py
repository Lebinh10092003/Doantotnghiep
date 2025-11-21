# apps/accounts/templatetags/group_tags.py
from django import template
from django.db.models import Q

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
        # SỬA LỖI: Sử dụng __iexact để không phân biệt chữ hoa/thường
        return user.groups.filter(name__iexact=group_name).exists()
    except Exception:
        return False

@register.filter
def in_any_group(user, group_names):
    """Kiểm tra xem người dùng có thuộc bất kỳ nhóm nào trong danh sách không (không phân biệt chữ hoa/thường)."""
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        names = [g.strip() for g in group_names.split(",")]
        query = Q()
        for name in names:
            query |= Q(name__iexact=name)
        return user.groups.filter(query).exists()
    except Exception:
        return False

@register.filter
def get_item(mapping, key):
    """
    Safe way to fetch a key from a mapping inside templates.
    """
    try:
        return mapping.get(key)
    except Exception:
        return None
