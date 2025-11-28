from django import forms 
from ..centers.models import Center, Room
from ..common.models import NamedModel
import json 

class CenterForm(forms.ModelForm):
    class Meta:
        model = Center
        fields = [
            'name',
            'code',
            'address',
            'phone',
            'email',
            'description',
            'avatar',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['name'].label = "Tên Trung tâm"
        self.fields['code'].label = "Mã Trung tâm"
        self.fields['address'].label = "Địa chỉ Trung tâm"
        self.fields['phone'].label = "Điện thoại Trung tâm"
        self.fields['email'].label = "Email Trung tâm"
        self.fields['description'].label = "Mô tả Trung tâm"
        self.fields['avatar'].label = "Ảnh đại diện Trung tâm"
        self.fields['is_active'].label = "Hoạt động"
    
    def clean_code(self):
        code = self.cleaned_data['code']
        if code:
            qs = Center.objects.filter(code__iexact=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError("Mã Trung tâm này đã tồn tại.")
        return code
    

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["center", "name", "note"]
        widgets = {
            "center": forms.Select(attrs={"class": "form-select tom-select"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "note": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["center"].label = "Trung tâm"
        self.fields["name"].label = "Tên phòng"
        self.fields["note"].label = "Ghi chú"


