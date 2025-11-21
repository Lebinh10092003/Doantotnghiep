import django_filters
from django import forms
from apps.students.models import StudentProduct
from apps.classes.models import Class


class StudentProductFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        field_name="title",
        lookup_expr="icontains",
        label="Tìm kiếm",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tiêu đề"}),
    )
    klass = django_filters.ModelChoiceFilter(
        field_name="session__klass",
        queryset=Class.objects.select_related("subject").all(),
        label="Lớp",
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
        model = StudentProduct
        fields = ["q", "klass", "start_date", "end_date"]
