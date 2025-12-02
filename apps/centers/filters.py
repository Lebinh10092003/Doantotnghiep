from django import forms
import django_filters
from django.db.models import Q

from .models import Center


class CenterFilter(django_filters.FilterSet):
    GROUP_BY_CHOICES = (
        ("", "Không nhóm"),
        ("status", "Nhóm theo trạng thái"),
    )

    STATUS_CHOICES = (
        ("", "Tất cả trạng thái"),
        ("active", "Hoạt động"),
        ("inactive", "Không hoạt động"),
    )

    q = django_filters.CharFilter(
        method="filter_search",
        label="Tìm kiếm",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tên, mã, địa chỉ, email hoặc số điện thoại",
            }
        ),
    )
    status = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method="filter_status",
        label="Trạng thái",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    group_by = django_filters.ChoiceFilter(
        choices=GROUP_BY_CHOICES,
        method="filter_group_by",
        label="Nhóm theo",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    class Meta:
        model = Center
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ẩn field nhóm trong form để UI riêng điều khiển giá trị.
        self.form.fields["group_by"].widget = forms.HiddenInput()
        self.group_by_value = ""

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        tokens = [token.strip() for token in value.split() if token.strip()]
        for token in tokens:
            queryset = queryset.filter(
                Q(name__icontains=token)
                | Q(code__icontains=token)
                | Q(address__icontains=token)
                | Q(phone__icontains=token)
                | Q(email__icontains=token)
            )
        return queryset

    def filter_status(self, queryset, name, value):
        if value == "active":
            return queryset.filter(is_active=True)
        if value == "inactive":
            return queryset.filter(is_active=False)
        return queryset

    def filter_group_by(self, queryset, name, value):
        self.group_by_value = value or ""
        return queryset
