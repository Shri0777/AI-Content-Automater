"""Tells Django about the notifications app."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Settings for the notifications app."""

    name = "notifications"
    default_auto_field = "django.db.models.BigAutoField"
