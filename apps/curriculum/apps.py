from django.apps import AppConfig


class CurriculumConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.curriculum"

    def ready(self):
        # Import signals để dọn file media khi xóa/clear
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Tránh lỗi khi migration chưa được áp dụng
            pass
