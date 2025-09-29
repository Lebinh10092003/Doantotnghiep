from django.db import models
from django.conf import settings


class Enrollment(models.Model):
    klass = models.ForeignKey(
        "classes.Class", on_delete=models.CASCADE, related_name="enrollments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    joined_at = models.DateField(auto_now_add=True)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)


class Meta:
    unique_together = (("klass", "student"),)
    indexes = [models.Index(fields=["klass"]), models.Index(fields=["student"])]


def __str__(self):
    return f"{self.student.username} → {self.klass.name}"
