import django_filters
from django.db.models import Q

from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.centers.models import Center


class BillingEnrollmentFilter(django_filters.FilterSet):
    student = django_filters.CharFilter(
        method="filter_student",
        label="Tài khoản học sinh",
    )
    klass_code = django_filters.CharFilter(
        field_name="klass__code", lookup_expr="icontains", label="Mã lớp"
    )
    center = django_filters.ModelChoiceFilter(
        queryset=Center.objects.all(),
        field_name="klass__center",
        label="Trung tâm",
    )
    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=EnrollmentStatus.choices,
        label="Trạng thái",
    )

    class Meta:
        model = Enrollment
        fields = ["student", "klass_code", "center", "status"]

    def filter_student(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(student__username__icontains=value)
            | Q(student__email__icontains=value)
            | Q(student__phone__icontains=value)
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes for UI consistency
        for name, field in self.form.fields.items():
            css = "form-control"
            if name in ["center", "status"]:
                css = "form-select"
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " " + css).strip()
