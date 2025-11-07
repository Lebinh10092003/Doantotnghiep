from django.apps import AppConfig


class CentersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.centers"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
