"""Tells Django about the core app (shared building blocks)."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Settings for the core app."""

    name = "core"
    default_auto_field = "django.db.models.BigAutoField"
