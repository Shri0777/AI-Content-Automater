"""Tells Django about the planning app."""

from django.apps import AppConfig


class PlanningConfig(AppConfig):
    """Settings for the planning app."""

    name = "planning"
    default_auto_field = "django.db.models.BigAutoField"
