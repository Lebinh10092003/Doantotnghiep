from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from steam_center.storages import MediaStorage
from django.conf import settings

GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]

class User(AbstractUser):
    user_code = models.CharField(max_length=10, unique=True, db_index=True, blank=True, null=True)
    role = models.CharField(max_length=20, default="STUDENT")

    center = models.ForeignKey(
        "centers.Center",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(
        upload_to="avatars/",
        storage=MediaStorage(),
        null=True, 
        blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    # Cho phép nhiều giá trị NULL, nhưng nếu có giá trị thì phải duy nhất
    national_id = models.CharField(max_length=32, blank=True, null=True, unique=True)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "accounts_user"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["center"]),
            models.Index(fields=["user_code"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"

    def preferred_full_name(self) -> str:
        """Return the best available human friendly name for the user."""
        full_name = super().get_full_name()
        if full_name:
            full_name = full_name.strip()
        if full_name:
            return full_name
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        if self.username:
            return self.username
        return "Chưa cập nhật"

    def preferred_email(self) -> str:
        """Return the user's email or an empty string when missing."""
        return (self.email or "").strip()

    def display_name_with_email(self) -> str:
        """Display helper that combines full name with email when possible."""
        name = self.preferred_full_name()
        email = self.preferred_email()
        if email and email.lower() not in name.lower():
            return f"{name} ({email})"
        if email and not name:
            return email
        if not name and not email:
            return "Chưa cập nhật"
        return name


class UserCodeCounter(models.Model):
    prefix = models.CharField(max_length=5, unique=True)
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_code(cls, prefix: str) -> str:
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(prefix=prefix)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{prefix}{counter.last_number:04d}"

    def __str__(self):
        return f"{self.prefix}-{self.last_number:04d}"


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
        constraints = [
            models.CheckConstraint(
                check=~models.Q(parent=models.F("student")),
                name="parent_diff_from_student",
            )
        ]

    def __str__(self):
        return f"{self.parent.username} → {self.student.username}"
