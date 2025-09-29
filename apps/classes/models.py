from django.db import models
from django.conf import settings
from apps.centers.models import Center, Room
from apps.curriculum.models import Subject, Module, Lesson
from apps.common.models import TimeStampedModel

CLASS_STATUS = [
    ("PLANNED", "Planned"),
    ("ONGOING", "Ongoing"),
    ("COMPLETED", "Completed"),
    ("CANCELLED", "Cancelled"),
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


SESSION_STATUS = [
    ("PLANNED", "Planned"),
    ("DONE", "Done"),
    ("MISSED", "Missed"),
    ("CANCELLED", "Cancelled"),
]


class ClassSession(TimeStampedModel):
    klass = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="sessions")
    index = models.PositiveIntegerField()
    date = models.DateField(null=True, blank=True)
    lesson = models.ForeignKey(Lesson, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default="PLANNED")
    teacher_override = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="taught_sessions",
    )
    room_override = models.ForeignKey(
        Room, null=True, blank=True, on_delete=models.SET_NULL
    )
    assistants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assisted_sessions"
    )


class Meta:
    unique_together = (("klass", "index"),)
    ordering = ["klass", "index"]


def __str__(self):
    return f"{self.klass.name} - Buổi {self.index}"
