from django import forms
from django.contrib.auth import get_user_model

from apps.rewards.models import RedemptionRequest, RewardItem
from apps.class_sessions.models import ClassSession

User = get_user_model()


class AwardPointsForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=User.objects.filter(role="STUDENT").order_by("last_name", "first_name"),
        label="Học viên",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    session = forms.ModelChoiceField(
        queryset=ClassSession.objects.select_related("klass").order_by("-date"),
        required=False,
        label="Buổi học (tùy chọn)",
        widget=forms.Select(attrs={"class": "form-select tom-select"}),
    )
    delta = forms.IntegerField(
        min_value=1,
        label="Số điểm",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Nhập số điểm cộng"}),
    )
    reason = forms.CharField(
        required=False,
        label="Lý do",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: Tham gia đầy đủ"}),
    )


class RedemptionRequestForm(forms.ModelForm):
    class Meta:
        model = RedemptionRequest
        fields = ["item", "quantity", "note"]
        widgets = {
            "item": forms.Select(attrs={"class": "form-select tom-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ghi chú (không bắt buộc)"}),
        }
        labels = {
            "item": "Phần quà",
            "quantity": "Số lượng",
            "note": "Ghi chú",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = RewardItem.objects.filter(is_active=True, stock__gt=0).order_by(
            "-stock", "cost"
        )

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity") or 0
        if qty <= 0:
            raise forms.ValidationError("Số lượng phải lớn hơn 0.")
        item: RewardItem = self.cleaned_data.get("item")
        if item and item.stock < qty:
            raise forms.ValidationError("Không đủ tồn kho.")
        return qty


class RewardItemForm(forms.ModelForm):
    class Meta:
        model = RewardItem
        fields = ["name", "image", "description", "cost", "stock", "is_active"]
        labels = {
            "name": "Tên quà",
            "image": "Ảnh minh họa",
            "description": "Mô tả",
            "cost": "Giá (điểm)",
            "stock": "Tồn kho",
            "is_active": "Kích hoạt",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "cost": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
