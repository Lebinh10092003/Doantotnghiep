import django_filters
from django_filters import rest_framework as filters
from django import forms
from .models import ClassSession, SESSION_STATUS
from apps.centers.models import Center
from apps.curriculum.models import Subject, Lesson
from apps.accounts.models import User

class ClassSessionFilter(filters.FilterSet):
    # Lọc lồng ghép (nested) từ app 'classes'
    klass__name = filters.CharFilter(
        field_name="klass__name", 
        lookup_expr="icontains",
        label="Tên lớp",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    klass__center = filters.ModelChoiceFilter(
        field_name="klass__center",
        queryset=Center.objects.all(),
        label="Trung tâm",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    klass__subject = filters.ModelChoiceFilter(
        field_name="klass__subject",
        queryset=Subject.objects.all(),
        label="Môn học",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Lọc theo trạng thái buổi học
    status = filters.ChoiceFilter(
        choices=SESSION_STATUS, 
        label="Trạng thái buổi học",
        widget=forms.Select(attrs={'class': 'form-select'})
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

    class Meta:
        model = ClassSession
        fields = ['klass__name', 'klass__center', 'klass__subject', 'status', 'lesson__title', 'date']