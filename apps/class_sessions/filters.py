import django_filters
from django_filters import rest_framework as filters
from django import forms
from django.db.models import Q
from .models import ClassSession, SESSION_STATUS
from apps.centers.models import Center
from apps.curriculum.models import Subject, Lesson
from apps.accounts.models import User

class ClassSessionFilter(filters.FilterSet):
    GROUP_BY_CHOICES = (
        ("", "Không nhóm"),
        ("subject", "Nhóm theo môn học"),
        ("center", "Nhóm theo cơ sở"),
        ("teacher", "Nhóm theo giáo viên"),
        ("status", "Nhóm theo trạng thái"),
        ("timeslot", "Nhóm theo khung giờ"),
        ("date", "Nhóm theo ngày học"),
    )

    # Lọc lớp theo tên/mã
    klass_query = filters.CharFilter(
        method="filter_klass_query",
        label="Tên/Mã lớp",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên/mã lớp'})
    )
    klass__center = filters.ModelChoiceFilter(
        field_name="klass__center",
        queryset=Center.objects.all(),
        label="Trung tâm",
        widget=forms.Select(attrs={'class': 'form-select tom-select'})
    )
    klass__subject = filters.ModelChoiceFilter(
        field_name="klass__subject",
        queryset=Subject.objects.all(),
        label="Môn học",
        widget=forms.Select(attrs={'class': 'form-select tom-select'})
    )
    
    # Lọc theo trạng thái buổi học
    status = filters.ChoiceFilter(
        choices=SESSION_STATUS, 
        label="Trạng thái buổi học",
        widget=forms.Select(attrs={'class': 'form-select tom-select'})
    )
    
    # Lọc theo bài học
    lesson__title = filters.CharFilter(
        field_name="lesson__title",
        lookup_expr="icontains",
        label="Tên bài học",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Lọc theo ngày
    date = filters.DateFromToRangeFilter(
        field_name="date",
        label="Ngày diễn ra",
        widget=django_filters.widgets.RangeWidget(attrs={
            'class': 'form-control',
            'type': 'date'
        })
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

    def filter_klass_query(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(klass__name__icontains=value) |
            Q(klass__code__icontains=value)
        )

    def filter_group_by(self, queryset, name, value):
        self.group_by_value = value or ""
        return queryset

    class Meta:
        model = ClassSession
        fields = ['klass_query', 'klass__center', 'klass__subject', 'status', 'lesson__title', 'date', 'group_by']
