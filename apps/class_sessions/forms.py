from django import forms
from django.db.models import Q

from .models import ClassSession, ClassSessionPhoto
from apps.accounts.models import User

class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        display = obj.display_name_with_email()
        if display:
            return display
        return obj.preferred_full_name() if hasattr(obj, "preferred_full_name") else obj.get_full_name() or (obj.email or obj.username)

class UserMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        display = obj.display_name_with_email()
        if display:
            return display
        return obj.preferred_full_name() if hasattr(obj, "preferred_full_name") else obj.get_full_name() or (obj.email or obj.username)

class ClassSessionForm(forms.ModelForm):
    teacher_filter = (
        Q(role__iexact="teacher")
        | Q(role__iexact="assistant")
        | Q(groups__name__iexact="teacher")
        | Q(groups__name__iexact="assistant")
    )

    teacher_override = UserChoiceField(
        queryset=User.objects.filter(teacher_filter, is_active=True)
        .order_by('first_name', 'last_name')
        .distinct(),
        required=False,
        label="Giáo viên thay thế",
        widget=forms.Select(attrs={'class': 'form-select tom-select'})
    )
    
    assistants = UserMultipleChoiceField(
        queryset=User.objects.filter(teacher_filter, is_active=True)
        .order_by('first_name', 'last_name')
        .distinct(),
        required=False,
        label="Trợ giảng (Buổi)",
        widget=forms.SelectMultiple(attrs={'class': 'form-select tom-select', 'multiple': 'multiple'})
    )

    class Meta:
        model = ClassSession
        fields = [
            'klass', 'index', 'date', 'start_time', 'end_time', 
            'lesson', 'status', 'teacher_override', 'room_override', 'assistants'
        ]
        widgets = {
            'klass': forms.Select(attrs={'class': 'form-select tom-select'}),
            'index': forms.NumberInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(
                format="%H:%M",
                attrs={'type': 'time', 'class': 'form-control', 'lang': 'en-GB', 'inputmode': 'numeric'}
            ),
            'end_time': forms.TimeInput(
                format="%H:%M",
                attrs={'type': 'time', 'class': 'form-control', 'lang': 'en-GB', 'inputmode': 'numeric'}
            ),
            'lesson': forms.Select(attrs={'class': 'form-select tom-select'}),
            'status': forms.Select(attrs={'class': 'form-select tom-select'}),
            'room_override': forms.Select(attrs={'class': 'form-select tom-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force 24h clock display/input regardless of locale defaults
        self.fields['start_time'].input_formats = ["%H:%M"]
        self.fields['end_time'].input_formats = ["%H:%M"]
        # Tự động chọn lớp học nếu được truyền vào
        if 'initial' in kwargs and 'klass' in kwargs['initial']:
            self.fields['klass'].queryset = self.fields['klass'].queryset.filter(pk=kwargs['initial']['klass'])


class ClassSessionPhotoForm(forms.ModelForm):
    class Meta:
        model = ClassSessionPhoto
        fields = ["image", "caption"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "environment"}),
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": "Chú thích (tùy chọn)"}),
        }
