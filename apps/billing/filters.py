import django_filters
from django import forms
from django.db.models import Q

from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.centers.models import Center


class BillingEnrollmentFilter(django_filters.FilterSet):
    student = django_filters.CharFilter(
        method="filter_student",
        label="Tài khoản học sinh",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tên, email hoặc số điện thoại",
            }
        ),
    )
    klass_code = django_filters.CharFilter(
        field_name="klass__code",
        lookup_expr="icontains",
        label="Mã lớp",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nhập mã lớp"}
        ),
    )
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        field_name="klass__center",
        label="Trung tâm",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=EnrollmentStatus.choices,
        label="Trạng thái",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    class Meta:
        model = Enrollment
        fields = ["student", "klass_code", "center", "status"]

    def filter_student(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(student__first_name__icontains=value)
            | Q(student__last_name__icontains=value)
            | Q(student__username__icontains=value)
            | Q(student__email__icontains=value)
            | Q(student__phone__icontains=value)
        )
