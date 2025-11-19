from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from apps.class_sessions.models import ClassSession
from apps.curriculum.models import Exercise
from steam_center.storages import MediaStorage

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
        upload_to="student_products/images/",
        storage=MediaStorage(),
        null=True,
        blank=True,
    )
    video = models.FileField(
        upload_to="student_products/videos/",
        storage=MediaStorage(),
        null=True,
        blank=True,
    )
    embed_code = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        unique_together = (("session", "student", "title"),)
        ordering = ["-created_at"]


    def __str__(self):
        return f"{self.student.username} - {self.title}"


class StudentExerciseSubmission(models.Model):
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    session = models.ForeignKey(
        ClassSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercise_submissions",
    )
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="exercise_submissions"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to="exercise_submissions/files/", 
        storage=MediaStorage(),
        null=True, 
        blank=True)
    link_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.username} -> Exercise #{self.exercise_id}"
