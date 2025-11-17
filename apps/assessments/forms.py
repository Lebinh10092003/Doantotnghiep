from django import forms
from .models import Assessment

class AssessmentForm(forms.ModelForm):
    score = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Điểm',
            'step': '0.1',
            'min': '0',
            'max': '10',
            'style': 'max-width: 80px;'
        })
    )
    remark = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nhận xét...'})
    )
    
    class Meta:
        model = Assessment
        fields = ['score', 'remark']