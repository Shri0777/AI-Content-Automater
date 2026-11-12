"""Tells Django about the publishing app."""

from django.apps import AppConfig


class PublishingConfig(AppConfig):
    """Settings for the publishing app."""

    name = "publishing"
    default_auto_field = "django.db.models.BigAutoField"
