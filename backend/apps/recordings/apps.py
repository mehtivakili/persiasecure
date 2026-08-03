from django.apps import AppConfig


class RecordingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recordings"
    verbose_name = "ضبط‌ها"

    def ready(self):
        from . import signals  # noqa: F401
