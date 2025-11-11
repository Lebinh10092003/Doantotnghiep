from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel
from apps.centers.models import Room
from apps.curriculum.models import Lesson

SESSION_STATUS = [
    ("PLANNED", "Planned"),
    ("DONE", "Done"),
    ("MISSED", "Missed"),
    ("CANCELLED", "Cancelled"),
]


class ClassSession(TimeStampedModel):
    # Quan hệ với app 'classes'
    klass = models.ForeignKey(
        "classes.Class", 
        on_delete=models.CASCADE, 
        related_name="sessions"
    )
    index = models.PositiveIntegerField()
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    lesson = models.ForeignKey(
        Lesson, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL
    )
    status = models.CharField(
        max_length=20, 
        choices=SESSION_STATUS, 
        default="PLANNED"
    )
    teacher_override = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="taught_sessions",
    )
    room_override = models.ForeignKey(
        Room, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL
    )
    assistants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name="assisted_sessions"
    )

    class Meta:
        unique_together = (("klass", "index"),)
        ordering = ["klass", "index"]

    def __str__(self):
        return f"{self.klass.name} - Buổi {self.index}"