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
