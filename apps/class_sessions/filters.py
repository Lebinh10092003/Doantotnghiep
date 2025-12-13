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


def _teacher_option_label(user):
    if not user:
        return ""
    display = getattr(user, "display_name_with_email", None)
    if callable(display):
        try:
            resolved = display()
        except TypeError:
            resolved = display
    else:
        resolved = display
    if resolved:
        return resolved
    full_name = (user.get_full_name() or "").strip()
    email = (user.email or "").strip()
    if full_name and email:
        return f"{full_name} ({email})"
    if full_name:
        return full_name
    if email:
        return email
    return user.username


class TeachingScheduleFilter(filters.FilterSet):
    start_date = filters.DateFilter(
        label="Từ ngày",
        field_name="date",
        lookup_expr="gte",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
    )
    end_date = filters.DateFilter(
        label="Đến ngày",
        field_name="date",
        lookup_expr="lte",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
    )
    teacher = filters.ModelChoiceFilter(
        queryset=User.objects.none(),
        label="Giáo viên",
        method="filter_teacher",
        widget=forms.Select(attrs={
            "class": "form-select tom-select",
            "data-placeholder": "Chọn giáo viên",
        }),
    )

    class Meta:
        model = ClassSession
        fields = ["start_date", "end_date", "teacher"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.allow_teacher_filter = kwargs.pop("allow_teacher_filter", False)
        super().__init__(*args, **kwargs)
        self.selected_date = None
        self.selected_teacher = None
        self.week_start = None
        self.week_end = None

        teacher_field = self.form.fields.get("teacher")
        if teacher_field:
            if self.allow_teacher_filter:
                teacher_field.queryset = (
                    User.objects.filter(
                        Q(groups__name__in=["Teacher", "TEACHER"]) | Q(role__iexact="TEACHER")
                    )
                    .distinct()
                    .order_by("last_name", "first_name", "username")
                )
                teacher_field.label_from_instance = _teacher_option_label
            else:
                self.form.fields.pop("teacher", None)

        if "start_date" in self.form.fields:
            self.form.fields["start_date"].widget.attrs.setdefault("placeholder", "dd/mm/yyyy")
        if "end_date" in self.form.fields:
            self.form.fields["end_date"].widget.attrs.setdefault("placeholder", "dd/mm/yyyy")

    def filter_teacher(self, queryset, name, value):
        if value:
            self.selected_teacher = value
        return queryset
