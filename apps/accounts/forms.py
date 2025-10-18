from django import forms
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from apps.centers.models import Center

User = get_user_model()


class CenterModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class AdminUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label="Xác nhận mật khẩu", widget=forms.PasswordInput, required=True)

    center = CenterModelChoiceField(
        queryset=Center.objects.order_by('name'),
        label="Trung tâm",
        required=False,
        empty_label="-- Chọn trung tâm --"
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by('name'),
        required=False,
        label="Nhóm quyền",
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = [
            'avatar', 'email', 'phone',
            'first_name', 'last_name',
            'is_active', 'center', 'is_staff', 'groups'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Gán lại label tiếng Việt
        self.fields['first_name'].label = "Họ"
        self.fields['last_name'].label = "Tên"
        self.fields['email'].label = "Email"
        self.fields['phone'].label = "Số điện thoại"
        self.fields['is_active'].label = "Kích hoạt"
        self.fields['is_staff'].label = "Quản trị viên"
        self.fields['avatar'].label = "Ảnh đại diện"

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
    password = forms.CharField(label="Đặt mật khẩu mới", widget=forms.PasswordInput, required=False)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by('name'),
        required=False,
        label="Nhóm quyền",
        widget=forms.CheckboxSelectMultiple
    )
    center = CenterModelChoiceField(
        queryset=Center.objects.order_by('name'),
        label="Trung tâm",
        required=False,
        empty_label="-- Chọn trung tâm --"
    )

    class Meta:
        model = User
        fields = [
            'avatar', 'email', 'phone',
            'first_name', 'last_name',
            'is_active', 'center', 'is_staff', 'groups'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Gán lại label tiếng Việt
        self.fields['first_name'].label = "Họ"
        self.fields['last_name'].label = "Tên"
        self.fields['email'].label = "Email"
        self.fields['phone'].label = "Số điện thoại"
        self.fields['is_active'].label = "Kích hoạt"
        self.fields['is_staff'].label = "Quản trị viên"
        self.fields['avatar'].label = "Ảnh đại diện"

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('password')
        if pwd:
            user.set_password(pwd)

        groups = self.cleaned_data.get('groups')
        if groups:
            user.role = groups.first().name
        else:
            user.role = None

        if commit:
            user.save()
            self.save_m2m()
        return user


class SimpleGroupForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'codename'
        ),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 12})
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']


class ImportUserForm(forms.Form):
    file = forms.FileField(label="Chọn file Excel/CSV")
