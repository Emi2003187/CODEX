from django.apps import AppConfig


class ConsultorioApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consultorio_API"

    def ready(self):
        """Import application signals at startup."""
        import consultorio_API.signals  # noqa: F401
