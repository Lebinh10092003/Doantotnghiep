from django import forms

from apps.billing.models import BillingEntry, Discount
from apps.enrollments.models import Enrollment
from apps.enrollments.services import apply_discount


class BillingPurchaseForm(forms.ModelForm):
    class Meta:
        model = BillingEntry
        fields = [
            "sessions",
            "unit_price",
            "discount",
            "note",
        ]
        widgets = {
            "sessions": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 1000}),
            "discount": forms.Select(attrs={"class": "form-select tom-select"}),
            "note": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, enrollment: Enrollment | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.enrollment = enrollment
        self.fields["discount"].queryset = Discount.objects.filter(active=True)
        if enrollment:
            self.fields.setdefault("enrollment", None)

    def save(self, commit=True):
        entry: BillingEntry = super().save(commit=False)
        entry.entry_type = BillingEntry.EntryType.PURCHASE
        if self.enrollment:
            entry.enrollment = self.enrollment
        discount = self.cleaned_data.get("discount")
        sessions = self.cleaned_data.get("sessions") or 0
        unit_price = self.cleaned_data.get("unit_price") or 0
        discount_amount, new_unit_price = apply_discount(discount, int(unit_price), int(sessions))
        entry.unit_price = new_unit_price
        entry.discount_amount = discount_amount
        entry.amount = max(new_unit_price * sessions, 0)
        if commit:
            entry.save()
        return entry


class DiscountForm(forms.ModelForm):
    class Meta:
        model = Discount
        fields = [
            "code",
            "name",
            "percent",
            "amount",
            "max_amount",
            "active",
            "start_date",
            "end_date",
            "usage_limit",
            "note",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "percent": forms.NumberInput(attrs={"class": "form-control", "step": 0.1, "min": 0}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": 1000, "min": 0}),
            "max_amount": forms.NumberInput(attrs={"class": "form-control", "step": 1000, "min": 0}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "usage_limit": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
