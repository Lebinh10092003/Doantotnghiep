from django.db import models
from apps.class_sessions.models import ClassSession

ATTEND_CHOICES = [("P", "Present"), ("A", "Absent"), ("L", "Late")]


class Attendance(models.Model):
    session = models.ForeignKey(
            ClassSession,
            on_delete=models.CASCADE, 
            related_name="attendances"
        )
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="attendances"
    )
    status = models.CharField(max_length=1, choices=ATTEND_CHOICES, default="P")
    note = models.CharField(max_length=255, blank=True)


class Meta:
    unique_together = (("session", "student"),)
    indexes = [models.Index(fields=["session"]), models.Index(fields=["student"])]
    ordering = ["-session__date", "student__username"]


def __str__(self):
    return f"{self.student.username} - {self.get_status_display()} ({self.session})"
