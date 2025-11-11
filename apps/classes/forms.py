from django import forms
from django.forms import inlineformset_factory
from .models import Class, ClassSchedule
from apps.accounts.models import User

class ClassForm(forms.ModelForm):
    # Lọc danh sách giáo viên
    main_teacher = forms.ModelChoiceField(
        queryset=User.objects.filter(role="TEACHER").order_by('first_name', 'last_name'),
        required=False,
        label="Giáo viên chính",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Lọc danh sách trợ giảng
    assistants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role__in=["ASSISTANT", "TEACHER"]).order_by('first_name', 'last_name'),
        required=False,
        label="Trợ giảng",
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Class
        fields = [
            'code', 'name', 'center', 'subject', 'status', 
            'main_teacher', 'room', 'start_date', 'end_date', 'note', 'assistants'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'center': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['main_teacher'].label = "Giáo viên chính"
        self.fields['assistants'].label = "Trợ giảng"


ClassScheduleFormSet = inlineformset_factory(
    Class,
    ClassSchedule,
    fields=('day_of_week', 'start_time', 'end_time'),
    extra=1,
    can_delete=True,
    widgets={
        'day_of_week': forms.Select(attrs={'class': 'form-select'}),
        'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
    }
)
        