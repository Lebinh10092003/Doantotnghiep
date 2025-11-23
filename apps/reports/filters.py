import django_filters

from apps.accounts.models import User
from apps.centers.models import Center
from apps.classes.models import Class
from apps.enrollments.models import Enrollment


class StudentReportFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(), field_name="klass__center", label="Trung tâm"
    )
    klass = django_filters.ModelChoiceFilter(
        queryset=Class.objects.all(), field_name="klass", label="Lớp"
    )
    student = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(role="STUDENT"), field_name="student", label="Học viên"
    )
    start_date = django_filters.DateFilter(
        field_name="klass__sessions__date",
        lookup_expr="gte",
        label="Từ ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="klass__sessions__date",
        lookup_expr="lte",
        label="Đến ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = Enrollment
        fields = ["center", "klass", "student", "start_date", "end_date"]
