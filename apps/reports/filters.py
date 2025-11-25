import django_filters
from django.db.models import Q

from apps.accounts.models import User
from apps.billing.models import BillingEntry
from apps.centers.models import Center
from apps.classes.models import Class
from apps.curriculum.models import Subject
from apps.enrollments.models import Enrollment
from apps.class_sessions.models import ClassSession


class StudentReportFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(), 
        field_name="klass__center", 
        label="Trung tâm",
        empty_label="Tất cả trung tâm",
        required=False
    )
    klass = django_filters.ModelChoiceFilter(
        queryset=Class.objects.all(), 
        field_name="klass", 
        label="Lớp",
        empty_label="Tất cả lớp",
        required=False
    )
    student = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(
            Q(role="STUDENT") | Q(groups__name__in=["Student", "STUDENT"])
        ).distinct(), 
        field_name="student", 
        label="Học viên",
        empty_label="Tất cả học viên",
        required=False
    )
    start_date = django_filters.DateFilter(
        field_name="klass__sessions__date",
        lookup_expr="gte",
        label="Từ ngày",
        required=False,
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="klass__sessions__date",
        lookup_expr="lte",
        label="Đến ngày",
        required=False,
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = Enrollment
        fields = ["center", "klass", "student", "start_date", "end_date"]


class RevenueReportFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        field_name="enrollment__klass__center",
        label="Trung tâm",
    )
    enrollment = django_filters.ModelChoiceFilter(
        queryset=Enrollment.objects.select_related("klass", "student"),
        field_name="enrollment",
        label="Ghi danh",
    )
    start_date = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte",
        label="Từ ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte",
        label="Đến ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = BillingEntry
        fields = ["center", "enrollment", "start_date", "end_date"]


class TeachingHoursReportFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        field_name="klass__center",
        label="Trung tâm",
    )
    person = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(
            Q(role__in=["TEACHER", "ASSISTANT", "ADMIN", "CENTER_MANAGER"]) | 
            Q(groups__name__in=["Teacher", "TEACHER", "Assistant", "ASSISTANT", "Admin", "ADMIN", "Center Manager", "CENTER_MANAGER"]) |
            Q(is_staff=True)
        ).distinct(),
        label="Giáo viên/Trợ giảng",
        method="filter_person",
    )
    start_date = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        label="Từ ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        label="Đến ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = ClassSession
        fields = ["center", "person", "start_date", "end_date"]

    def filter_person(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(klass__main_teacher=value)
            | Q(teacher_override=value)
            | Q(assistants=value)
        ).distinct()


class ClassActivityReportFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        field_name="center",
        label="Trung tâm",
    )
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.all(),
        field_name="subject",
        label="Môn học",
    )
    main_teacher = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(
            Q(role__in=["TEACHER", "CENTER_MANAGER", "ADMIN"]) | 
            Q(groups__name__in=["Teacher", "TEACHER", "Center Manager", "CENTER_MANAGER", "Admin", "ADMIN"])
        ).distinct(),
        field_name="main_teacher",
        label="Giáo viên chính",
    )
    start_date = django_filters.DateFilter(
        field_name="sessions__date",
        lookup_expr="gte",
        label="Từ ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="sessions__date",
        lookup_expr="lte",
        label="Đến ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = Class
        fields = ["center", "subject", "main_teacher", "start_date", "end_date"]


class EnrollmentSummaryFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        field_name="klass__center",
        label="Trung tâm",
        empty_label="Tất cả trung tâm",
        required=False,
    )
    start_date = django_filters.DateFilter(
        field_name="joined_at",
        lookup_expr="gte",
        label="Từ ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="joined_at",
        lookup_expr="lte",
        label="Đến ngày",
        widget=django_filters.widgets.forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = Enrollment
        fields = ["center", "start_date", "end_date"]
