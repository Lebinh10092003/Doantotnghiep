# apps/accounts/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.forms import (
    PasswordChangeForm as DjangoPasswordChangeForm,
    SetPasswordForm as DjangoSetPasswordForm,
)
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.text import slugify
from django.db.models import Q

from apps.centers.models import Center

User = get_user_model()


# ===== Helpers =====
cccd_validator = RegexValidator(
    regex=r"^\d{12}$",
    message="CCCD phải gồm đúng 12 chữ số."
)

def detect_prefix_from_groups(groups_qs) -> str:
    if not groups_qs:
        return "US"
    name = groups_qs.first().name.upper()
    if name in {"TEACHER", "ADMIN", "ASSISTANT", "STAFF", "CENTER_MANAGER"}:
        return "EDS"
    if name == "PARENT":
        return "PR"
    if name == "STUDENT":
        return "ST"
    return "US"


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
        self.fields['phone'].required = False 
        self.fields['is_active'].label = "Kích hoạt"
        self.fields['is_staff'].label = "Quản trị viên"
        self.fields['dob'].label = "Ngày sinh"
        self.fields['dob'].widget = forms.DateInput(attrs={'type': 'date'})
        self.fields['gender'].label = "Giới tính"
        self.fields['national_id'].label = "Số CCCD/CMND"
        self.fields['address'].label = "Địa chỉ"
        self.fields['avatar'].label = "Ảnh đại diện"

    # --- validators ---
    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        if not nid:
            return nid  # cho phép để trống
        cccd_validator(nid)
        if User.objects.filter(national_id=nid).exists():
            raise ValidationError("CCCD đã tồn tại trong hệ thống.")
        return nid

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Mật khẩu và xác nhận mật khẩu không trùng.")

        groups = cleaned.get("groups") or []
        phone = (cleaned.get("phone") or "").strip()
        is_student_role = any(getattr(g, "name", "").upper() == "STUDENT" for g in groups)
        if not is_student_role and not phone:
            self.add_error("phone", "Số điện thoại là bắt buộc cho vai trò này.")
        cleaned["phone"] = phone
        return cleaned

    def save(self, commit=True):
        # import tại đây để tránh vòng lặp import
        from .models import UserCodeCounter

        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])

        # username duy nhất từ họ tên
        base = slugify(f"{self.cleaned_data.get('first_name','')} {self.cleaned_data.get('last_name','')}") or "user"
        username = base
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base}{i}"
        user.username = username

        # sinh user_code theo nhóm đã chọn trong form
        groups = self.cleaned_data.get('groups')
        prefix = detect_prefix_from_groups(groups)
        user.user_code = UserCodeCounter.next_code(prefix)

        if commit:
            user.save()
            self.save_m2m()
            selected_groups = groups or self.cleaned_data.get('groups')
            first_group = None
            if selected_groups:
                try:
                    first_group = selected_groups[0]
                except (TypeError, KeyError, IndexError):
                    first_group = selected_groups.first()

            new_role = (first_group.name if first_group else None) or user.role or User._meta.get_field('role').default or 'STUDENT'
            if user.role != new_role:
                user.role = new_role
                user.save(update_fields=['role'])

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
            'is_active', 'center', 'is_staff', 'groups',
            'national_id', 'address'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = "Họ"
        self.fields['last_name'].label = "Tên"
        self.fields['email'].label = "Email"
        self.fields['phone'].label = "Số điện thoại"
        self.fields['phone'].required = False  
        self.fields['is_active'].label = "Kích hoạt"
        self.fields['is_staff'].label = "Quản trị viên"
        self.fields['avatar'].label = "Ảnh đại diện"
        self.fields['national_id'].label = "Số CCCD/CMND"
        self.fields['address'].label = "Địa chỉ"

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        if not nid:
            return nid
        cccd_validator(nid)
        if User.objects.filter(national_id=nid).exclude(pk=self.instance.pk).exists():
            raise ValidationError("CCCD đã tồn tại trong hệ thống.")
        return nid

    def clean(self):
        cleaned = super().clean()
        groups = cleaned.get("groups")
        # Khi form edit không chọn groups mới, dùng nhóm hiện tại của instance
        effective_groups = list(groups) if groups is not None else list(self.instance.groups.all())
        phone = (cleaned.get("phone") or "").strip()
        is_student_role = any(getattr(g, "name", "").upper() == "STUDENT" for g in effective_groups)
        if not is_student_role and not phone:
            self.add_error("phone", "Số điện thoại là bắt buộc cho vai trò này.")
        cleaned["phone"] = phone
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)

        if commit:
            user.save()
            self.save_m2m()
            groups = self.cleaned_data.get('groups')
            first_group = None
            if groups:
                try:
                    first_group = groups[0]
                except (TypeError, KeyError, IndexError):
                    first_group = groups.first()

            new_role = (first_group.name if first_group else None) or user.role or User._meta.get_field('role').default or 'STUDENT'
            if user.role != new_role:
                user.role = new_role
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
        # Import local để tránh lỗi Circular Import
        from apps.accounts.views import PROTECTED_GROUPS 
        
        super().__init__(*args, **kwargs)
        self.fields['name'].label = "Tên nhóm"

        # --- LOGIC NGĂN SỬA TÊN NHÓM HỆ THỐNG ---
        # Kiểm tra xem form có đang edit 1 instance (1 nhóm) đã tồn tại không
        if self.instance and self.instance.pk:
            # Nếu tên của nhóm này nằm trong danh sách được bảo vệ
            if self.instance.name in PROTECTED_GROUPS:
                # Đặt trường 'name' thành chỉ đọc (readonly)
                self.fields['name'].widget.attrs['readonly'] = True
        # ------------------------------------------

    def clean_name(self):
        """
        Thêm validation ở backend để đảm bảo tên nhóm hệ thống không bị đổi,
        ngay cả khi ai đó cố tình bypass thuộc tính 'readonly' ở frontend.
        """
        # Import local để tránh lỗi Circular Import
        from apps.accounts.views import PROTECTED_GROUPS 

        name = self.cleaned_data.get('name')
        
        # Chỉ kiểm tra khi đang edit (self.instance.pk tồn tại)
        if self.instance and self.instance.pk:
            # Kiểm tra xem tên *gốc* của nhóm có được bảo vệ không
            if self.instance.name in PROTECTED_GROUPS:
                # Nếu tên mới không khớp với tên gốc (nghĩa là người dùng cố tình đổi)
                if name != self.instance.name:
                    raise forms.ValidationError(
                        f"Không thể đổi tên nhóm hệ thống '{self.instance.name}'."
                    )
        
        return name


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

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        if not nid:
            return nid
        cccd_validator(nid)
        if User.objects.filter(national_id=nid).exclude(pk=self.instance.pk).exists():
            raise ValidationError("CCCD đã tồn tại trong hệ thống.")
        return nid


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
        self.error_messages['password_mismatch'] = "Mật khẩu xác nhận không khớp. Vui lòng nhập lại."
        self.fields['new_password1'].validators = []
        self.fields['new_password2'].validators = []
        self.fields['new_password1'].help_text = "Gợi ý: kết hợp chữ và số để mật khẩu khó đoán hơn, nhưng chúng tôi không bắt buộc định dạng cụ thể."
        self.fields['new_password2'].help_text = "Nhập lại mật khẩu mới để xác nhận."

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if not password1 or not password2:
            raise ValidationError('Vui lòng nhập đầy đủ mật khẩu mới.')
        if password1 != password2:
            raise ValidationError(self.error_messages['password_mismatch'], code='password_mismatch')
        return password2


class UserSetPasswordForm(DjangoSetPasswordForm):
    """Customized reset form sharing copy with change-password version."""

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['new_password1'].label = "Mật khẩu mới"
        self.fields['new_password1'].validators = []
        self.fields['new_password2'].validators = []
        self.fields['new_password1'].help_text = "Chọn mật khẩu mà bạn dễ nhớ. Không có yêu cầu định dạng đặc biệt."
        self.fields['new_password2'].label = "Xác nhận mật khẩu mới"
        self.fields['new_password2'].help_text = "Nhập lại mật khẩu mới để xác nhận."

        self.error_messages['password_mismatch'] = "Mật khẩu xác nhận không khớp. Vui lòng nhập lại."

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if not password1 or not password2:
            raise ValidationError('Vui lòng nhập đầy đủ mật khẩu mới.')
        if password1 != password2:
            raise ValidationError(self.error_messages['password_mismatch'], code='password_mismatch')
        return password2


class ForgotPasswordForm(forms.Form):
    identifier = forms.CharField(
        label="Email hoặc số điện thoại",
        widget=forms.TextInput(attrs={"placeholder": "Nhập email hoặc số điện thoại"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_cache = None

    def clean_identifier(self):
        identifier = (self.cleaned_data.get("identifier") or "").strip()
        if not identifier:
            raise forms.ValidationError("Vui lòng nhập email hoặc số điện thoại đã đăng ký.")

        lookup = Q(email__iexact=identifier) | Q(phone__iexact=identifier)
        if identifier.isdigit():
            lookup = lookup | Q(username__iexact=identifier)

        self.user_cache = User.objects.filter(lookup, is_active=True).first()
        return identifier

    def get_user(self):
        return self.user_cache
