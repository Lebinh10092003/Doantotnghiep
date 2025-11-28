import django_filters
from django import forms
from django.db.models import Q

from .models import Subject, Module, Lesson, Exercise

YES_NO_CHOICES = (
    ("", "Tất cả"),
    ("yes", "Có"),
    ("no", "Không"),
)


class SubjectFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(
        method="filter_query",
        label="Từ khóa",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Tên, mã hoặc mô tả"}
        ),
    )
    has_avatar = django_filters.ChoiceFilter(
        method="filter_has_avatar",
        choices=YES_NO_CHOICES,
        label="Ảnh đại diện",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    class Meta:
        model = Subject
        fields = ["query", "has_avatar"]

    def filter_query(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(code__icontains=value)
            | Q(description__icontains=value)
        )

    def filter_has_avatar(self, queryset, name, value):
        if value == "yes":
            return queryset.exclude(avatar="").exclude(avatar__isnull=True)
        if value == "no":
            return queryset.filter(Q(avatar="") | Q(avatar__isnull=True))
        return queryset


class ModuleFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(
        method="filter_query",
        label="Từ khóa",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Tiêu đề, mô tả, môn học"}
        ),
    )
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.order_by("name"),
        label="Môn học",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    has_image = django_filters.ChoiceFilter(
        method="filter_has_image",
        label="Ảnh minh họa",
        choices=YES_NO_CHOICES,
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    class Meta:
        model = Module
        fields = ["query", "subject", "has_image"]

    def filter_query(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(subject__name__icontains=value)
            | Q(subject__code__icontains=value)
        )

    def filter_has_image(self, queryset, name, value):
        if value == "yes":
            return queryset.exclude(image="").exclude(image__isnull=True)
        if value == "no":
            return queryset.filter(Q(image="") | Q(image__isnull=True))
        return queryset


class LessonFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(
        method="filter_query",
        label="Từ khóa",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Tiêu đề, học phần, môn học"}
        ),
    )
    subject = django_filters.ModelChoiceFilter(
        queryset=Subject.objects.order_by("name"),
        label="Môn học",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    module = django_filters.ModelChoiceFilter(
        queryset=Module.objects.none(),
        label="Học phần",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    has_lecture = django_filters.ChoiceFilter(
        method="filter_has_lecture",
        choices=YES_NO_CHOICES,
        label="Có bài giảng",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    has_exercise = django_filters.ChoiceFilter(
        method="filter_has_exercise",
        choices=YES_NO_CHOICES,
        label="Có bài tập",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    exercise_difficulty = django_filters.ChoiceFilter(
        field_name="exercise__difficulty",
        choices=Exercise._meta.get_field("difficulty").choices,
        label="Độ khó bài tập",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )

    class Meta:
        model = Lesson
        fields = [
            "query",
            "subject",
            "module",
            "has_lecture",
            "has_exercise",
            "exercise_difficulty",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        module_field = self.form.fields.get("module")
        if module_field:
            module_field.queryset = Module.objects.order_by("title")
            subject_value = self.data.get("subject") or self.form.initial.get("subject")
            try:
                if subject_value:
                    module_field.queryset = module_field.queryset.filter(subject_id=int(subject_value))
            except (TypeError, ValueError):
                pass

    def filter_query(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(module__title__icontains=value)
            | Q(module__subject__name__icontains=value)
            | Q(module__subject__code__icontains=value)
        )

    def filter_has_lecture(self, queryset, name, value):
        if value == "yes":
            return queryset.filter(lecture__isnull=False)
        if value == "no":
            return queryset.filter(lecture__isnull=True)
        return queryset

    def filter_has_exercise(self, queryset, name, value):
        if value == "yes":
            return queryset.filter(exercise__isnull=False)
        if value == "no":
            return queryset.filter(exercise__isnull=True)
        return queryset
