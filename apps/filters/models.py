from django.db import models
from django.conf import settings

class SavedFilter(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="saved_filters"
    )
    name = models.CharField(max_length=255)
    model_name = models.CharField(
        max_length=100, 
        db_index=True, 
        help_text="Tên model, ví dụ: 'Class' hoặc 'ClassSession'"
    )
    query_params = models.JSONField(
        default=dict, 
        help_text="Các tham số GET của bộ lọc, lưu dưới dạng JSON"
    )
    is_public = models.BooleanField(
        default=False, 
        help_text="Những người dùng khác có thể thấy bộ lọc này không?"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user", "name"]
        indexes = [
            models.Index(fields=["model_name", "user"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.model_name})"