from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditoria'

    def ready(self):
        # Liga os avisos de login e de erro de login.
        from . import signals  # noqa: F401