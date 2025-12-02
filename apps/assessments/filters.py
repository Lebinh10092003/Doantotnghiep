import django_filters
from django import forms
from django.db.models import Q

from apps.accounts.models import User
from .models import Assessment
from apps.centers.models import Center
from apps.classes.models import Class


def apply_assessment_search(queryset, value: str):
    if not value:
        return queryset
    value = value.strip()
    if not value:
        return queryset
    lookup = (
        Q(student__first_name__icontains=value)
        | Q(student__last_name__icontains=value)
        | Q(student__username__icontains=value)
        | Q(student__email__icontains=value)
        | Q(session__klass__name__icontains=value)
        | Q(session__klass__code__icontains=value)
        | Q(session__klass__center__name__icontains=value)
        | Q(remark__icontains=value)
    )
    return queryset.filter(lookup)


def apply_student_search(queryset, value: str):
    if not value:
        return queryset
    value = value.strip()
    if not value:
        return queryset
    lookup = (
        Q(first_name__icontains=value)
        | Q(last_name__icontains=value)
        | Q(username__icontains=value)
        | Q(email__icontains=value)
    )
    return queryset.filter(lookup)


class AssessmentRecordFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all().order_by("name"),
        field_name="session__klass__center",
        label="Trung tâm",
        empty_label="Tất cả trung tâm",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    klass = django_filters.ModelChoiceFilter(
        queryset=Class.objects.all().order_by("name"),
        field_name="session__klass",
        label="Lớp học",
        empty_label="Tất cả lớp",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    score_status = django_filters.ChoiceFilter(
        choices=(
            ("scored", "Đã chấm điểm"),
            ("pending", "Chưa chấm"),
        ),
        label="Trạng thái điểm",
        method="filter_score_status",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    start_date = django_filters.DateFilter(
        field_name="session__date",
        lookup_expr="gte",
        label="Từ ngày",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="session__date",
        lookup_expr="lte",
        label="Đến ngày",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    search = django_filters.CharFilter(
        method="filter_search",
        label="Từ khóa",
        field_name="q",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tên học sinh, lớp, trung tâm, ghi chú...",
            }
        ),
    )

    class Meta:
        model = Assessment
        fields = ["center", "klass", "score_status", "start_date", "end_date"]

    def filter_score_status(self, queryset, name, value):
        if value == "scored":
            return queryset.filter(score__isnull=False)
        if value == "pending":
            return queryset.filter(score__isnull=True)
        return queryset

    def filter_search(self, queryset, name, value):
        return apply_assessment_search(queryset, value)


class StudentAssessmentFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all().order_by("name"),
        field_name="center",
        label="Trung tâm",
        empty_label="Tất cả trung tâm",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    start_date = django_filters.DateFilter(
        field_name="assessments__session__date",
        lookup_expr="gte",
        label="Từ ngày",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="assessments__session__date",
        lookup_expr="lte",
        label="Đến ngày",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    search = django_filters.CharFilter(
        method="filter_search",
        label="Từ khóa",
        field_name="q",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tên, email hoặc tài khoản học sinh",
            }
        ),
    )

    distinct = True

    class Meta:
        model = User
        fields = ["center", "start_date", "end_date"]

    def filter_search(self, queryset, name, value):
        return apply_student_search(queryset, value)


class AssessmentSummaryFilter(django_filters.FilterSet):
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all().order_by("name"),
        field_name="session__klass__center",
        label="Trung tâm",
        empty_label="Tất cả trung tâm",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    start_date = django_filters.DateFilter(
        field_name="session__date",
        lookup_expr="gte",
        label="Từ ngày",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = django_filters.DateFilter(
        field_name="session__date",
        lookup_expr="lte",
        label="Đến ngày",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = Assessment
        fields = ["center", "start_date", "end_date"]
