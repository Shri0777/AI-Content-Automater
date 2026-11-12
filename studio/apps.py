"""Tells Django about the studio app."""

from django.apps import AppConfig


class StudioConfig(AppConfig):
    """Settings for the studio app."""

    name = "studio"
    default_auto_field = "django.db.models.BigAutoField"
