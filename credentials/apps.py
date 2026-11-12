"""Tells Django about the credentials app."""

from django.apps import AppConfig


class CredentialsConfig(AppConfig):
    """Settings for the credentials app."""

    name = "credentials"
    default_auto_field = "django.db.models.BigAutoField"
