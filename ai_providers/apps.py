from django.apps import AppConfig


class AiProvidersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_providers'

    def ready(self):
        from .services.registry import registry
        registry.register_defaults()
