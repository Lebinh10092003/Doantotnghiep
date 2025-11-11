import django_filters
from django_filters import rest_framework as filters
from django import forms # <-- THÊM IMPORT NÀY
from .models import Class, CLASS_STATUS
from apps.centers.models import Center
from apps.curriculum.models import Subject
from apps.accounts.models import User

class ClassFilter(filters.FilterSet):
    # Lọc văn bản (tên lớp, mã lớp)
    name = filters.CharFilter(
        field_name="name", 
        lookup_expr="icontains", 
        label="Tên hoặc Mã lớp",
        widget=forms.TextInput(attrs={'class': 'form-control'}) # <-- THÊM WIDGET
    )
    
    # Lọc theo lựa chọn (status)
    status = filters.ChoiceFilter(
        choices=CLASS_STATUS, 
        label="Trạng thái",
        widget=forms.Select(attrs={'class': 'form-select'}) # <-- THÊM WIDGET
    )
    
    # Lọc theo Foreign Key (Center, Subject, Teacher)
    center = filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        label="Trung tâm",
        widget=forms.Select(attrs={'class': 'form-select'}) # <-- THÊM WIDGET
    )
    subject = filters.ModelChoiceFilter(
        queryset=Subject.objects.all(),
        label="Môn học",
        widget=forms.Select(attrs={'class': 'form-select'}) # <-- THÊM WIDGET
    )
    main_teacher = filters.ModelChoiceFilter(
        queryset=User.objects.filter(role="TEACHER").order_by('first_name', 'last_name'),
        label="Giáo viên chính",
        widget=forms.Select(attrs={'class': 'form-select'}) # <-- THÊM WIDGET
    )
    
    # Lọc theo khoảng ngày
    start_date = filters.DateFromToRangeFilter(
        field_name="start_date",
        label="Ngày bắt đầu (từ... đến...)",
        widget=django_filters.widgets.RangeWidget(attrs={ # <-- THÊM WIDGET
            'class': 'form-control',
            'type': 'date'
        })
    )

    class Meta:
        model = Class
        fields = ['name', 'status', 'center', 'subject', 'main_teacher', 'start_date']