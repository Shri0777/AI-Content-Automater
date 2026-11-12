"""Tells Django about the quotas app (free-tier limits)."""

from django.apps import AppConfig


class QuotasConfig(AppConfig):
    """Settings for the quotas app."""

    name = "quotas"
    default_auto_field = "django.db.models.BigAutoField"
