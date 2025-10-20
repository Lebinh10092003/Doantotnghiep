from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings




GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]


class User(AbstractUser):
    role = models.CharField(max_length=20,default="STUDENT")
    center = models.ForeignKey(
        "centers.Center",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    phone = models.CharField(max_length=20, blank=False)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    national_id = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)


    class Meta:
        db_table = "accounts_user"
        indexes = [models.Index(fields=["role"]), models.Index(fields=["center"])]


    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class ParentStudentRelation(models.Model):
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="children_relations",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_relations",
    )
    note = models.CharField(max_length=255, blank=True)


    class Meta:
        unique_together = (("parent", "student"),)
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["student"])]


    def __str__(self):
        return f"{self.parent.username} → {self.student.username}"
