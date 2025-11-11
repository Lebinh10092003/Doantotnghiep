from django import forms
from .models import SavedFilter

class SavedFilterForm(forms.ModelForm):
    class Meta:
        model = SavedFilter
        fields = ["name", "is_public", "model_name", "query_params"]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Các trường này sẽ là hidden
            'model_name': forms.HiddenInput(),
            'query_params': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = "Tên bộ lọc"
        self.fields['is_public'].label = "Chia sẻ (công khai)"