from django.db import models
from django.conf import settings


class EnrollmentStatus(models.TextChoices):
    NEW = "NEW", "Mới"
    ACTIVE = "ACTIVE", "Đang học"
    PAUSED = "PAUSED", "Bảo lưu"
    COMPLETED = "COMPLETED", "Hoàn tất"
    CANCELLED = "CANCELLED", "Nghỉ học"


class Enrollment(models.Model):
    klass = models.ForeignKey(
        "classes.Class", on_delete=models.CASCADE, related_name="enrollments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.NEW,
    )
    fee_per_session = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=300000,
        help_text="Đơn giá mỗi buổi (VND)",
    )
    sessions_purchased = models.PositiveIntegerField(
        default=0, help_text="Số buổi mua (nếu nhập số buổi)"
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Số tiền đã đóng (VND, nếu nhập tiền sẽ tự tính buổi)",
    )
    sessions_consumed = models.PositiveIntegerField(
        default=0,
        help_text="Số buổi đã sử dụng (tự động tính từ điểm danh)",
    )
    joined_at = models.DateField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["klass"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
        ]

    ACTIVE_STATUSES = {EnrollmentStatus.NEW, EnrollmentStatus.ACTIVE}

    def save(self, *args, **kwargs):
        self.active = self.status in self.ACTIVE_STATUSES
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.username} - {self.klass.name}"

    @property
    def sessions_from_payment(self) -> int:
        if self.fee_per_session and self.amount_paid:
            return int(self.amount_paid // self.fee_per_session)
        return 0

    @property
    def sessions_total(self) -> int:
        try:
            from apps.enrollments import services

            return services.total_sessions_purchased(self)
        except Exception:
            return max(self.sessions_purchased, self.sessions_from_payment)

    @property
    def sessions_remaining(self) -> int:
        try:
            from apps.enrollments import services

            return services.sessions_remaining(self)
        except Exception:
            remaining = max(self.sessions_total - self.sessions_consumed, 0)
        return remaining

    @property
    def projected_end_date(self):
        try:
            from apps.enrollments import services

            return services.project_end_date(self.start_date, self.sessions_total, self.klass)
        except Exception:
            return None


class EnrollmentStatusLog(models.Model):
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="status_logs"
    )
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    reason = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.enrollment_id}: {self.old_status} -> {self.new_status} ({self.reason})"
