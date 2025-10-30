from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from apps.centers.models import Center
import re
from django.utils.text import slugify
import random

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
            'first_name', 'last_name', 'dob', 'gender',
            'national_id', 'address',
            'is_active', 'center', 'is_staff', 'groups'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = "Họ"
        self.fields['last_name'].label = "Tên"
        self.fields['email'].label = "Email"
        self.fields['phone'].label = "Số điện thoại"
        self.fields['is_active'].label = "Kích hoạt"
        self.fields['is_staff'].label = "Quản trị viên"
        self.fields['dob'].label = "Ngày sinh"
        self.fields['dob'].widget = forms.DateInput(attrs={'type': 'date'})
        self.fields['gender'].label = "Giới tính"
        self.fields['national_id'].label = "Số CCCD/CMND"
        self.fields['address'].label = "Địa chỉ"
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

        # Tự động tạo username duy nhất
        first_name = self.cleaned_data.get('first_name', '')
        last_name = self.cleaned_data.get('last_name', '')
        
        # Tạo username cơ bản từ tên
        base_username = slugify(f"{first_name} {last_name}") or "user"
        username = base_username
        counter = 1
        # Đảm bảo username là duy nhất
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username

        if commit:
            user.save() # Lưu người dùng trước để có ID
            self.save_m2m() # Lưu các quan hệ ManyToMany (groups)

            # Sau khi groups đã được lưu, gán giá trị cho trường role
            groups = self.cleaned_data.get('groups')
            user.role = groups.first().name if groups else None
            user.save(update_fields=['role']) # Chỉ cập nhật trường 'role'

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
        self.fields['first_name'].label = "Họ"
        self.fields['last_name'].label = "Tên"
        self.fields['email'].label = "Email"
        self.fields['phone'].label = "Số điện thoại"
        self.fields['is_active'].label = "Kích hoạt"
        self.fields['is_staff'].label = "Quản trị viên"
        self.fields['avatar'].label = "Ảnh đại diện"

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')

        # Chỉ đặt mật khẩu mới nếu người dùng nhập vào trường password
        if password:
            user.set_password(password)

        if commit:
            user.save()
            # Lưu các quan hệ ManyToMany (bao gồm cả groups)
            self.save_m2m()

            # Sau khi groups đã được lưu, cập nhật lại trường `role`
            groups = self.cleaned_data.get('groups')
            user.role = groups.first().name if groups.exists() else None
            user.save(update_fields=['role'])

        return user


class SimpleGroupForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'codename'
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Quyền hạn"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = "Tên nhóm"


class ImportUserForm(forms.Form):
    file = forms.FileField(label="Chọn file Excel/CSV")


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'avatar',
            'dob', 'gender', 'national_id', 'address'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = "Họ"
        self.fields['last_name'].label = "Tên"
        self.fields['email'].label = "Email"
        self.fields['phone'].label = "Số điện thoại"
        self.fields['avatar'].label = "Ảnh đại diện"
        self.fields['dob'].label = "Ngày sinh"
        self.fields['dob'].widget = forms.DateInput(attrs={'type': 'date'})
        self.fields['gender'].label = "Giới tính"
        self.fields['national_id'].label = "Số CCCD/CMND"
        self.fields['address'].label = "Địa chỉ"
        self.fields['address'].widget = forms.Textarea(attrs={'rows': 3})


class UserPasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['old_password'].label = "Mật khẩu cũ"
        self.fields['old_password'].error_messages = {
            'required': 'Vui lòng nhập mật khẩu cũ của bạn.',
            'password_incorrect': 'Mật khẩu cũ của bạn không đúng. Vui lòng nhập lại.'
        }

        self.fields['new_password1'].label = "Mật khẩu mới"
        self.fields['new_password1'].error_messages = {
            'required': 'Vui lòng nhập mật khẩu mới.'
        }

        self.fields['new_password2'].label = "Xác nhận mật khẩu mới"
        self.fields['new_password2'].error_messages = {
            'required': 'Vui lòng xác nhận mật khẩu mới.',
        }

        self.fields['new_password1'].help_text = (
            "<ul>"
            "<li>Không được quá giống với các thông tin cá nhân khác.</li>"
            "<li>Phải chứa ít nhất 8 ký tự.</li>"
            "<li>Không thể là một mật khẩu được sử dụng phổ biến.</li>"
            "<li>Không thể chỉ chứa số.</li>"
            "</ul>"
        )

        # Ghi đè thông báo lỗi non-field error cho trường hợp mật khẩu không khớp
        self.error_messages['password_mismatch'] = "Mật khẩu xác nhận không khớp. Vui lòng nhập lại."

        # Ghi đè thông báo lỗi của các validators mặc định
        for validator in self.fields['new_password1'].validators:
            if isinstance(validator, password_validation.MinimumLengthValidator):
                validator.message = 'Mật khẩu phải chứa ít nhất %(min_length)d ký tự.'
            elif isinstance(validator, password_validation.UserAttributeSimilarityValidator):
                validator.message = 'Mật khẩu quá giống với thông tin cá nhân khác của bạn.'
            elif isinstance(validator, password_validation.CommonPasswordValidator):
                validator.message = 'Mật khẩu quá phổ biến. Vui lòng chọn mật khẩu khác.'
            elif isinstance(validator, password_validation.NumericPasswordValidator):
                validator.message = 'Mật khẩu không được chỉ chứa các chữ số.'

        self.fields['new_password2'].help_text = "Nhập lại mật khẩu mới để xác nhận."
