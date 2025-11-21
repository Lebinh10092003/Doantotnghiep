from django.db import models
from django.utils import timezone


class Discount(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Giảm % (0-100)"
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=0, default=0, help_text="Giảm cố định (VND)"
    )
    max_amount = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, help_text="Trần giảm giá (VND)"
    )
    active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Số lần dùng tối đa")
    usage_count = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class BillingEntry(models.Model):
    class EntryType(models.TextChoices):
        PURCHASE = "PURCHASE", "Purchase"
        CONSUME = "CONSUME", "Consume"
        ADJUST = "ADJUST", "Adjust"

    enrollment = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="billing_entries",
    )
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Amount in VND (đã trừ giảm giá nếu có)",
    )
    sessions = models.IntegerField(
        default=0,
        help_text="Positive for purchase/adjust up, negative for consume/adjust down",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Đơn giá áp dụng (VND/buổi) sau giảm",
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Số tiền giảm cho entry này",
    )
    discount = models.ForeignKey(
        Discount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_entries",
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entry_type} {self.sessions} sessions for {self.enrollment_id}"
