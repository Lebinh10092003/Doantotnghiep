from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Meta:
    ordering = ["-created_at"]
    indexes = [models.Index(fields=["user"]), models.Index(fields=["is_read"])]


def __str__(self):
    return f"{self.user.username}: {self.title}"
    