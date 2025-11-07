from django.apps import AppConfig


class CurriculumConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.curriculum"

    def ready(self):
        # Import signals to handle media file cleanup on delete/clear
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Avoid crashing if migrations not applied yet
            pass
