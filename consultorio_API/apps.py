from django.apps import AppConfig


class ConsultorioApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'consultorio_API'

from django.apps import AppConfig
class ConsultorioApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consultorio_API"

    def ready(self):
        from . import signals   # noqa
        
        
class ConsultorioApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consultorio_API"

    def ready(self):
        # Importa las señales al arrancar
        import consultorio_API.signals  # noqa: F401
