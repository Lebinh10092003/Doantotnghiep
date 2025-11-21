import django_filters
from django import forms
from django.db.models import Q
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.centers.models import Center
from apps.classes.models import Class
from apps.accounts.models import User


class EnrollmentFilter(django_filters.FilterSet):
    klass = django_filters.ModelChoiceFilter(
        queryset=Class.objects.select_related("center", "subject").all(),
        label="Lớp",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        label="Trung tâm",
        field_name="klass__center",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    status = django_filters.ChoiceFilter(
        choices=EnrollmentStatus.choices,
        label="Trạng thái",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    student = django_filters.CharFilter(
        method="filter_student",
        label="Học viên",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Họ tên / phone / mã"}
        ),
    )
    start_date = django_filters.DateFromToRangeFilter(
        field_name="start_date",
        label="Ngày bắt đầu",
        widget=django_filters.widgets.RangeWidget(
            attrs={"class": "form-control", "type": "date"}
        ),
    )
    end_date = django_filters.DateFromToRangeFilter(
        field_name="end_date",
        label="Ngày kết thúc",
        widget=django_filters.widgets.RangeWidget(
            attrs={"class": "form-control", "type": "date"}
        ),
    )

    def filter_student(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(student__first_name__icontains=value)
            | Q(student__last_name__icontains=value)
            | Q(student__phone__icontains=value)
            | Q(student__user_code__icontains=value)
        )

    class Meta:
        model = Enrollment
        fields = ["klass", "center", "status", "student", "start_date", "end_date"]
