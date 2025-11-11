from django import forms
from django.forms import inlineformset_factory
from .models import Class, ClassSchedule
from apps.accounts.models import User


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.get_full_name() or obj.username} ({obj.email} - {obj.username})"


class UserMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.get_full_name() or obj.username} ({obj.email} - {obj.username})"


class ClassForm(forms.ModelForm):
    # Lọc danh sách giáo viên
    main_teacher = UserChoiceField(
        queryset=User.objects.filter(role="TEACHER").order_by("first_name", "last_name"),
        required=False,
        label="Giáo viên chính",
        widget=forms.Select(attrs={"class": "form-select tom-select"}), # Đảm bảo class tom-select
    )

    # Lọc danh sách trợ giảng
    assistants = UserMultipleChoiceField(
        queryset=User.objects.filter(role__in=["ASSISTANT", "TEACHER"]).order_by("first_name", "last_name"),
        required=False,
        label="Trợ giảng",
        widget=forms.SelectMultiple(attrs={"class": "form-select tom-select", "multiple": "multiple"}), # Đảm bảo class tom-select
    )

    class Meta:
        model = Class
        fields = [
            "code",
            "name",
            "center",
            "subject",
            "status",
            "main_teacher",
            "room",
            "start_date",
            "end_date",
            "note",
            "assistants",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "center": forms.Select(attrs={"class": "form-select tom-select"}),
            "subject": forms.Select(attrs={"class": "form-select tom-select"}),
            "status": forms.Select(attrs={"class": "form-select tom-select"}),
            "room": forms.Select(attrs={"class": "form-select tom-select"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["main_teacher"].label = "Giáo viên chính"
        self.fields["assistants"].label = "Trợ giảng"

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "Ngày kết thúc phải >= ngày bắt đầu.")
        return cleaned

    def clean_assistants(self):
        assistants = self.cleaned_data.get("assistants")
        main_teacher = self.cleaned_data.get("main_teacher")
        if main_teacher and assistants and main_teacher in assistants:
            raise forms.ValidationError("Giáo viên chính không được nằm trong danh sách trợ giảng.")
        return assistants


# Formset lịch học (một bản duy nhất, không trùng)
ClassScheduleFormSet = inlineformset_factory(
    parent_model=Class,
    model=ClassSchedule,
    fields=("day_of_week", "start_time", "end_time"),
    extra=1,
    can_delete=True,
    min_num=0,           # đổi thành >=1 nếu muốn bắt buộc
    validate_min=False,  # đổi thành True nếu muốn bắt buộc
    widgets={
        "day_of_week": forms.Select(attrs={"class": "form-select"}),
        "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    },
)
