from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.models import Group

from apps.accounts.forms import cccd_validator
from apps.accounts.models import ParentStudentRelation, UserCodeCounter
from apps.billing.models import Discount
from apps.enrollments.models import Enrollment, EnrollmentStatus

User = get_user_model()
GENDER_CHOICES = User._meta.get_field("gender").choices or []


class EnrollmentForm(forms.ModelForm):
    # Tạo mới khách hàng (học sinh mới) và tùy chọn gắn phụ huynh hiện có hoặc tạo mới phụ huynh
    create_customer = forms.BooleanField(required=False, label="Tạo mới khách hàng (học sinh mới)")
    student_username = forms.CharField(required=False, label="Tên đăng nhập học sinh")
    student_password = forms.CharField(required=False, label="Mật khẩu học sinh", widget=forms.PasswordInput)
    student_full_name = forms.CharField(required=False, label="Họ tên học sinh")
    student_phone = forms.CharField(required=False, label="Số điện thoại học sinh")
    student_email = forms.EmailField(required=False, label="Email học sinh")
    student_dob = forms.DateField(
        required=False,
        label="Ngày sinh học sinh",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    student_gender = forms.ChoiceField(
        required=False,
        label="Giới tính học sinh",
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    student_national_id = forms.CharField(
        required=False,
        label="CCCD/CMND học sinh",
        max_length=32,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    student_address = forms.CharField(
        required=False,
        label="Địa chỉ học sinh",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    parent_existing = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Phụ huynh hiện có",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    parent_full_name = forms.CharField(required=False, label="Họ tên phụ huynh")
    parent_phone = forms.CharField(required=False, label="Số điện thoại phụ huynh")
    parent_email = forms.EmailField(required=False, label="Email phụ huynh")
    parent_dob = forms.DateField(
        required=False,
        label="Ngày sinh phụ huynh",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    parent_gender = forms.ChoiceField(
        required=False,
        label="Giới tính phụ huynh",
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    parent_national_id = forms.CharField(
        required=False,
        label="CCCD/CMND phụ huynh",
        max_length=32,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    parent_address = forms.CharField(
        required=False,
        label="Địa chỉ phụ huynh",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    discount = forms.ModelChoiceField(
        queryset=Discount.objects.none(),
        required=False,
        label="Mã giảm giá",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Enrollment
        fields = [
            "student",
            "klass",
            "status",
            "start_date",
            "end_date",
            "fee_per_session",
            "sessions_purchased",
            "amount_paid",
            "discount",
            "note",
        ]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "fee_per_session": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 1000}),
            "sessions_purchased": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "amount_paid": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "step": 1000,
                }
            ),
            "discount": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        klass_queryset = kwargs.pop("klass_queryset", None)
        super().__init__(*args, **kwargs)

        base_students = User.objects.filter(role="STUDENT")
        if self.instance and self.instance.pk and self.instance.student_id:
            base_students = base_students | User.objects.filter(pk=self.instance.student_id)
        field_student = self.fields["student"]
        field_student.queryset = base_students.order_by("last_name", "first_name").distinct()
        field_student.label_from_instance = (
            lambda obj: f"{obj.get_full_name() or obj.username} | {obj.email or '-'} | {obj.phone or '-'} | {obj.national_id or '-'}"
        )
        field_student.widget.attrs.update(
            {
                "class": "form-select tom-select",
                "placeholder": "Tìm học sinh theo tên / email / SĐT / CCCD",
            }
        )
        field_student.required = False

        parent_qs = User.objects.filter(role="PARENT")
        self.fields["parent_existing"].queryset = parent_qs.order_by("last_name", "first_name").distinct()
        self.fields["parent_existing"].label_from_instance = (
            lambda obj: f"{obj.get_full_name() or obj.username} | {obj.email or '-'} | {obj.phone or '-'} | {obj.national_id or '-'}"
        )
        self.fields["parent_existing"].widget.attrs.update(
            {
                "class": "form-select tom-select",
                "placeholder": "Chọn phụ huynh hiện có (tên/email/SĐT/CCCD)",
            }
        )

        self.fields["klass"].widget.attrs.update({"class": "form-select"})
        self.fields["status"].widget.attrs.update({"class": "form-select"})
        if klass_queryset is not None:
            self.fields["klass"].queryset = klass_queryset

        self.fields["discount"].queryset = Discount.objects.filter(active=True).order_by("code")
    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        klass = cleaned.get("klass")
        status = cleaned.get("status")
        create_customer = cleaned.get("create_customer")
        parent_existing = cleaned.get("parent_existing")

        if not create_customer and not student:
            raise ValidationError("Chọn học viên hoặc bật 'Tạo mới khách hàng'.")

        if create_customer and student:
            self.add_error("student", "Khi tạo mới khách hàng không cần chọn học viên cũ.")

        if create_customer:
            required_fields = [
                ("student_username", "Nhập tên đăng nhập học sinh."),
                ("student_password", "Nhập mật khẩu học sinh."),
                ("student_full_name", "Nhập họ tên học sinh."),
                ("student_dob", "Chọn ngày sinh học sinh."),
                ("student_gender", "Chọn giới tính học sinh."),
                ("student_national_id", "Nhập CCCD/CMND học sinh."),
                ("student_address", "Nhập địa chỉ học sinh."),
            ]
            for field, message in required_fields:
                if not cleaned.get(field):
                    self.add_error(field, message)
            if cleaned.get("student_phone") and User.objects.filter(phone=cleaned["student_phone"]).exists():
                self.add_error("student_phone", "Số điện thoại đã được dùng cho tài khoản khác.")
            if cleaned.get("student_email") and User.objects.filter(email=cleaned["student_email"]).exists():
                self.add_error("student_email", "Email đã được dùng cho tài khoản khác.")
            if cleaned.get("student_national_id"):
                try:
                    cccd_validator(cleaned["student_national_id"])
                except ValidationError as exc:
                    self.add_error("student_national_id", exc.message)
                if User.objects.filter(national_id=cleaned["student_national_id"]).exists():
                    self.add_error("student_national_id", "CCCD đã được dùng cho tài khoản khác.")

            if not parent_existing:
                required_parent = [
                    ("parent_full_name", "Nhập họ tên phụ huynh."),
                    ("parent_phone", "Nhập số điện thoại phụ huynh."),
                    ("parent_email", "Nhập email phụ huynh."),
                    ("parent_dob", "Chọn ngày sinh phụ huynh."),
                    ("parent_gender", "Chọn giới tính phụ huynh."),
                    ("parent_national_id", "Nhập CCCD/CMND phụ huynh."),
                    ("parent_address", "Nhập địa chỉ phụ huynh."),
                ]
                for field, message in required_parent:
                    if not cleaned.get(field):
                        self.add_error(field, message)
                if cleaned.get("parent_phone") and User.objects.filter(phone=cleaned["parent_phone"]).exists():
                    self.add_error("parent_phone", "Số điện thoại đã được dùng cho tài khoản khác.")
                if cleaned.get("parent_email") and User.objects.filter(email=cleaned["parent_email"]).exists():
                    self.add_error("parent_email", "Email đã được dùng cho tài khoản khác.")
                if cleaned.get("parent_national_id"):
                    try:
                        cccd_validator(cleaned["parent_national_id"])
                    except ValidationError as exc:
                        self.add_error("parent_national_id", exc.message)
                    if User.objects.filter(national_id=cleaned["parent_national_id"]).exists():
                        self.add_error("parent_national_id", "CCCD đã được dùng cho tài khoản khác.")

        if not create_customer and student and klass and status in (EnrollmentStatus.NEW, EnrollmentStatus.ACTIVE):
            qs = Enrollment.objects.filter(student=student, klass=klass, active=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Học viên này đã có ghi danh đang hoạt động trong lớp.")

        fee = cleaned.get("fee_per_session") or 0
        sessions = cleaned.get("sessions_purchased") or 0
        amount = cleaned.get("amount_paid") or 0
        if sessions <= 0 and amount <= 0:
            self.add_error("sessions_purchased", "Nhập số buổi mua hoặc số tiền.")
        if sessions <= 0 and amount > 0 and fee:
            cleaned["sessions_purchased"] = int(amount // fee) or 0
        return cleaned

    def _unique_username(self, base: str) -> str:
        base = base.strip() or "user"
        username = base
        idx = 1
        while User.objects.filter(username=username).exists():
            idx += 1
            username = f"{base}{idx}"
        return username

    def _split_name(self, full_name: str):
        parts = (full_name or "").strip().split(None, 1)
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    def _password_source(self, role: str) -> str:
        """
        Choose a password seed: phone if có, else CCCD, else mặc định '123456'.
        """
        if role == "STUDENT":
            return (
                (self.cleaned_data.get("student_phone") or "").strip()
                or (self.cleaned_data.get("student_national_id") or "").strip()
                or "123456"
            )
        return (
            (self.cleaned_data.get("parent_phone") or "").strip()
            or (self.cleaned_data.get("parent_national_id") or "").strip()
            or "123456"
        )

    def _create_user(self, *, full_name: str, phone: str, email: str, role: str, center=None):
        if role == "STUDENT":
            requested_username = (self.cleaned_data.get("student_username") or "").strip()
            if requested_username:
                if User.objects.filter(username=requested_username).exists():
                    raise ValidationError("Tên đăng nhập học sinh đã tồn tại, vui lòng chọn tên khác.")
                username = requested_username
            else:
                username = self._unique_username(phone or full_name or "user")
        else:
            username = self._unique_username(phone or full_name or "user")
        last_name, first_name = self._split_name(full_name)
        prefix = "ST" if role == "STUDENT" else "PR"
        user = User(
            username=username,
            phone=phone,
            email=email or "",
            role=role,
            center=center,
            last_name=last_name,
            first_name=first_name,
            is_active=True,
            user_code=UserCodeCounter.next_code(prefix),
        )
        if role == "STUDENT":
            user.dob = self.cleaned_data.get("student_dob")
            user.gender = self.cleaned_data.get("student_gender") or ""
            user.national_id = self.cleaned_data.get("student_national_id") or ""
            user.address = self.cleaned_data.get("student_address") or ""
        else:
            user.dob = self.cleaned_data.get("parent_dob")
            user.gender = self.cleaned_data.get("parent_gender") or ""
            user.national_id = self.cleaned_data.get("parent_national_id") or ""
            user.address = self.cleaned_data.get("parent_address") or ""
        pwd_source = self._password_source(role)
        user.set_password(pwd_source[-6:] if len(pwd_source) >= 6 else pwd_source)
        user.save()
        # Thêm vào group tương ứng với role nếu có
        try:
            group_name = "Student" if role == "STUDENT" else "Parent"
            grp = Group.objects.filter(name__iexact=group_name).first()
            if grp:
                user.groups.add(grp)
        except Exception:
            pass
        return user

    @transaction.atomic
    def save(self, commit=True):
        create_customer = self.cleaned_data.get("create_customer")
        parent_existing = self.cleaned_data.get("parent_existing")
        klass = self.cleaned_data.get("klass")

        if create_customer:
            student = self._create_user(
                full_name=self.cleaned_data.get("student_full_name", ""),
                phone=self.cleaned_data.get("student_phone", ""),
                email=self.cleaned_data.get("student_email", ""),
                role="STUDENT",
                center=getattr(klass, "center", None),
            )
            self.instance.student = student

        instance = super().save(commit=False)

        if commit:
            instance.save()

        if create_customer:
            if parent_existing:
                ParentStudentRelation.objects.get_or_create(parent=parent_existing, student=instance.student)
            else:
                parent = self._create_user(
                    full_name=self.cleaned_data.get("parent_full_name", ""),
                    phone=self.cleaned_data.get("parent_phone", ""),
                    email=self.cleaned_data.get("parent_email", ""),
                    role="PARENT",
                    center=getattr(klass, "center", None),
                )
                ParentStudentRelation.objects.get_or_create(parent=parent, student=instance.student)
        elif parent_existing and instance.student_id:
            ParentStudentRelation.objects.get_or_create(parent=parent_existing, student=instance.student)

        if commit:
            instance.save()

        return instance
