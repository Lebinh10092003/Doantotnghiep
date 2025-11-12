from django.db import models
from apps.class_sessions.models import ClassSession


class StudentProduct(models.Model):
    session = models.ForeignKey(
            ClassSession,
            on_delete=models.CASCADE,
            related_name="student_products",
        )
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="student_products"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="student_products/images/", null=True, blank=True
    )
    video = models.FileField(
        upload_to="student_products/videos/", null=True, blank=True
    )
    embed_code = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        unique_together = (("session", "student", "title"),)
        ordering = ["-created_at"]


    def __str__(self):
        return f"{self.student.username} - {self.title}"
