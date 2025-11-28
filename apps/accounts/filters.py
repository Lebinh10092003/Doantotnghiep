from django import forms
import django_filters
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from apps.centers.models import Center


User = get_user_model()


class UserFilter(django_filters.FilterSet):
    STATUS_CHOICES = (
        ("", "Tất cả trạng thái"),
        ("active", "Hoạt động"),
        ("inactive", "Không hoạt động"),
    )
    BOOLEAN_CHOICES = (
        ("", "Tất cả"),
        ("1", "Có"),
        ("0", "Không"),
    )
    GROUP_BY_CHOICES = (
        ("", "Không nhóm"),
        ("role", "Nhóm theo vai trò"),
        ("center", "Nhóm theo trung tâm"),
    )

    q = django_filters.CharFilter(method="filter_search", label="Từ khóa")
    status = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES, method="filter_status", label="Trạng thái"
    )
    role = django_filters.ChoiceFilter(
        label="Vai trò", choices=(), field_name="groups__name", lookup_expr="exact"
    )
    group = django_filters.ModelChoiceFilter(
        queryset=Group.objects.none(), label="Nhóm (Group)", field_name="groups"
    )
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.none(), label="Trung tâm"
    )
    is_staff = django_filters.ChoiceFilter(
        choices=BOOLEAN_CHOICES, method="filter_is_staff", label="Là nhân viên?"
    )
    is_superuser = django_filters.ChoiceFilter(
        choices=BOOLEAN_CHOICES, method="filter_is_superuser", label="Là superuser?"
    )
    date_joined_from = django_filters.DateFilter(
        field_name="date_joined", lookup_expr="date__gte", label="Ngày tạo từ"
    )
    date_joined_to = django_filters.DateFilter(
        field_name="date_joined", lookup_expr="date__lte", label="Ngày tạo đến"
    )
    last_login_from = django_filters.DateFilter(
        field_name="last_login", lookup_expr="date__gte", label="Đăng nhập cuối từ"
    )
    last_login_to = django_filters.DateFilter(
        field_name="last_login", lookup_expr="date__lte", label="Đăng nhập cuối đến"
    )
    group_by = django_filters.ChoiceFilter(
        choices=GROUP_BY_CHOICES, method="filter_group_by", label="Nhóm theo"
    )

    class Meta:
        model = User
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        group_qs = Group.objects.order_by("name")
        self.filters["group"].queryset = group_qs
        self.filters["center"].queryset = Center.objects.order_by("name")
        self.filters["role"].extra["choices"] = [
            (name, name) for name in group_qs.values_list("name", flat=True)
        ]
        # Ẩn field nhóm trong form chung – UI riêng sẽ điều khiển giá trị này.
        self.form.fields["group_by"].widget = forms.HiddenInput()
        self.group_by_value = ""

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        tokens = [token.strip() for token in value.split() if token.strip()]
        for token in tokens:
            queryset = queryset.filter(
                Q(first_name__icontains=token)
                | Q(last_name__icontains=token)
                | Q(email__icontains=token)
                | Q(phone__icontains=token)
                | Q(username__icontains=token)
            )
        return queryset

    def filter_status(self, queryset, name, value):
        if value == "active":
            return queryset.filter(is_active=True)
        if value == "inactive":
            return queryset.filter(is_active=False)
        return queryset

    def _apply_boolean(self, queryset, field_name, value):
        if value == "1":
            return queryset.filter(**{field_name: True})
        if value == "0":
            return queryset.filter(**{field_name: False})
        return queryset

    def filter_is_staff(self, queryset, name, value):
        return self._apply_boolean(queryset, "is_staff", value)

    def filter_is_superuser(self, queryset, name, value):
        return self._apply_boolean(queryset, "is_superuser", value)

    def filter_group_by(self, queryset, name, value):
        self.group_by_value = value or ""
        return queryset
