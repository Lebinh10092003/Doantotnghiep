from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

User = get_user_model()

class AdminUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label="Xác nhận mật khẩu", widget=forms.PasswordInput, required=True)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.order_by('name'), required=False)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'groups']

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Mật khẩu và xác nhận mật khẩu không trùng.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            self.save_m2m()
        return user

class AdminUserUpdateForm(forms.ModelForm):
    # optional password change
    password = forms.CharField(label="Đặt mật khẩu mới", widget=forms.PasswordInput, required=False)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.order_by('name'), required=False)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'groups']

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('password')
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
            self.save_m2m()
        return user

class SimpleGroupForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').order_by('content_type__app_label','codename'),
        required=False,
        widget=forms.SelectMultiple(attrs={'size':12})
    )
    class Meta:
        model = Group
        fields = ['name','permissions']
