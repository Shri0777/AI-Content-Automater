"""Tells Django about the newsroom app."""

from django.apps import AppConfig


class NewsroomConfig(AppConfig):
    """Settings for the newsroom app."""

    name = "newsroom"
    default_auto_field = "django.db.models.BigAutoField"
