from django.apps import AppConfig


class CamerasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cameras"
    verbose_name = "دوربین‌ها"

    def ready(self):
        from . import signals  # noqa: F401
