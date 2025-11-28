import django_filters
from django_filters import rest_framework as filters
from django import forms
from django.db.models import Q

from .models import Class, CLASS_STATUS
from apps.centers.models import Center
from apps.curriculum.models import Subject
from apps.accounts.models import User


class ClassFilter(filters.FilterSet):
    GROUP_BY_CHOICES = (
        ("", "Không nhóm"),
        ("subject", "Nhóm theo môn"),
        ("center", "Nhóm theo cơ sở"),
        ("teacher", "Nhóm theo giáo viên"),
        ("status", "Nhóm theo trạng thái"),
        ("timeslot", "Nhóm theo khung giờ"),
    )

    # Lọc theo tên hoặc mã lớp
    query = filters.CharFilter(
        method="filter_query",
        label="Tên hoặc Mã lớp",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nhập tên/mã lớp"}),
    )

    status = filters.ChoiceFilter(
        choices=CLASS_STATUS,
        label="Trạng thái",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    center = filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        label="Trung tâm",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    subject = filters.ModelChoiceFilter(
        queryset=Subject.objects.all(),
        label="Môn học",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    main_teacher = filters.ModelChoiceFilter(
        queryset=User.objects.filter(role="TEACHER").order_by("first_name", "last_name"),
        label="Giáo viên chính",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    start_date = filters.DateFromToRangeFilter(
        field_name="start_date",
        label="Ngày bắt đầu (từ... đến...)",
        widget=django_filters.widgets.RangeWidget(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    group_by = filters.ChoiceFilter(
        choices=GROUP_BY_CHOICES,
        label="Nhóm theo",
        method="filter_group_by",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.fields["group_by"].widget = forms.HiddenInput()
        self.group_by_value = ""

    def filter_query(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))

    def filter_group_by(self, queryset, name, value):
        self.group_by_value = value or ""
        return queryset

    class Meta:
        model = Class
        fields = [
            "query",
            "status",
            "center",
            "subject",
            "main_teacher",
            "start_date",
            "group_by",
        ]
