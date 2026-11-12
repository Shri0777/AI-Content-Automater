"""Tells Django about the accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Settings for the accounts app."""

    name = "accounts"
    default_auto_field = "django.db.models.BigAutoField"
