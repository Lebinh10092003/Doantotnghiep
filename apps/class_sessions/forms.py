from django import forms
from .models import ClassSession
from apps.accounts.models import User
from apps.classes.models import Class
from apps.curriculum.models import Lesson

class ClassSessionForm(forms.ModelForm):
    # Tối ưu hóa querysets
    klass = forms.ModelChoiceField(
        queryset=Class.objects.select_related('center', 'subject').order_by('name'),
        label="Lớp học",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    lesson = forms.ModelChoiceField(
        queryset=Lesson.objects.select_related('module__subject').order_by('module__subject__name', 'module__order', 'order'),
        required=False,
        label="Bài học",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    teacher_override = forms.ModelChoiceField(
        queryset=User.objects.filter(role="TEACHER").order_by('first_name', 'last_name'),
        required=False,
        label="GV thay thế",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    assistants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role__in=["ASSISTANT", "TEACHER"]).order_by('first_name', 'last_name'),
        required=False,
        label="Trợ giảng (Buổi)",
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ClassSession
        fields = [
            'klass', 'index', 'date', 'start_time', 'end_time', 
            'lesson', 'status', 'teacher_override', 'room_override', 'assistants'
        ]
        widgets = {
            'index': forms.NumberInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'room_override': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'index': 'Thứ tự buổi',
            'date': 'Ngày học',
            'start_time': 'Giờ bắt đầu',
            'end_time': 'Giờ kết thúc',
            'status': 'Trạng thái',
            'room_override': 'Phòng học (thay thế)',
        }