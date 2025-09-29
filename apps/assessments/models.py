from django.db import models


class Assessment(models.Model):
    session = models.ForeignKey(
        "classes.ClassSession", on_delete=models.CASCADE, related_name="assessments"
    )
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="assessments"
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=255, blank=True)


class Meta:
    unique_together = (("session", "student"),)


def __str__(self):
    return f"{self.student.username} - {self.session}: {self.score}"
