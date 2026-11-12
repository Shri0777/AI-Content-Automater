"""Tells Django about the social app."""

from django.apps import AppConfig


class SocialConfig(AppConfig):
    """Settings for the social app."""

    name = "social"
    default_auto_field = "django.db.models.BigAutoField"
