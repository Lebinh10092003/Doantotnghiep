from django import forms 
from ..centers.models import Center
from ..common.models import NamedModel
import json 

class CenterForm(forms.ModelForm):
    class Meta:
        model = Center
        fields = ['name','code','address','phone','description','avatar','is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['name'].label = "Center Name"
        self.fields['code'].label = "Center Code"
        self.fields['address'].label = "Center Address"
        self.fields['phone'].label = "Center Phone"
        self.fields['description'].label = "Center Description"
        self.fields['avatar'].label = "Center Avatar"
        self.fields['is_active'].label = "Is Active"
    
    def clean_code(self):
        code = self.cleaned_data['code']
        if code:
            qs = Center.objects.filter(code__iexact=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError("Mã Trung tâm này đã tồn tại.")
        return code
    

    

