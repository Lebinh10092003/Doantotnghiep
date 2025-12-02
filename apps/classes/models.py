from django.db import models
from django.conf import settings
from apps.centers.models import Center, Room
from apps.curriculum.models import Subject
from apps.common.models import TimeStampedModel

CLASS_STATUS = [
    ("PLANNED", "Kế hoạch"),
    ("ONGOING", "Đang diễn ra"),
    ("COMPLETED", "Đã hoàn thành"),
    ("CANCELLED", "Đã hủy"),
]


class Class(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    center = models.ForeignKey(Center, on_delete=models.PROTECT, related_name="classes")
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="classes"
    )
    status = models.CharField(max_length=20, choices=CLASS_STATUS, default="PLANNED")
    main_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="main_classes",
    )
    room = models.ForeignKey(
        Room,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="classes_optional",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    assistants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ClassAssistant",
        related_name="assist_classes",
        blank=True,
    )

    def __str__(self):
        return f"{self.code} - {self.name}"

class ClassSchedule(models.Model):
    """
    Lưu lịch học cố định hàng tuần cho một lớp học.
    Ví dụ: Thứ 2 (8:00-9:30), Thứ 5 (14:00-15:30)
    """
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Thứ Hai"
        TUESDAY = 1, "Thứ Ba"
        WEDNESDAY = 2, "Thứ Tư"
        THURSDAY = 3, "Thứ Năm"
        FRIDAY = 4, "Thứ Sáu"
        SATURDAY = 5, "Thứ Bảy"
        SUNDAY = 6, "Chủ Nhật"

    klass = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="weekly_schedules")
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = (("klass", "day_of_week", "start_time"),)
        ordering = ["klass", "day_of_week", "start_time"]

class ClassAssistant(models.Model):
    klass = models.ForeignKey(Class, on_delete=models.CASCADE)
    assistant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scope = models.CharField(
        max_length=20,
        choices=[("COURSE", "Whole Course"), ("SESSION", "Per Session")],
        default="COURSE",
    )

    class Meta:
        unique_together = (("klass", "assistant", "scope"),)

    def __str__(self):
        return f"{self.assistant.username} → {self.klass.name} ({self.scope})"