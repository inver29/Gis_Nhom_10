from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "myapp"
    verbose_name = "QU\u1ea2N L\u00dd NGHI\u1ec6P V\u1ee4"

    def ready(self):
        from . import signals  # noqa: F401
