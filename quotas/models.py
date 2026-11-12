"""Database tables for free-tier limits.

QuotaPolicy  - the limit for one resource on one tier ("free users: 3 plans")
QuotaOverride - a different limit for one particular user, set by the operator
QuotaUsage   - how much of a daily limit a user has used on a given day
"""

import uuid

from django.conf import settings
from django.db import models

PERIOD_CHOICES = [
    ("day", "Per day"),
    ("total", "At any time"),
    ("setting", "Fixed setting"),
]

APPLIES_TO_CHOICES = [
    ("account", "The whole account"),
    ("plan", "Each content plan"),
    ("post", "Each post"),
    ("kind", "Each kind of credential"),
]


class QuotaPolicy(models.Model):
    """The limit for one resource on one tier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tier = models.CharField(max_length=32)
    resource = models.CharField(max_length=64)
    limit_value = models.PositiveIntegerField()
    period = models.CharField(max_length=16, choices=PERIOD_CHOICES)
    applies_to = models.CharField(max_length=16, choices=APPLIES_TO_CHOICES)
    description = models.CharField(max_length=200)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tier", "resource"], name="one_policy_per_tier_and_resource"
            )
        ]
        verbose_name_plural = "quota policies"

    def __str__(self):
        return f"{self.tier}: {self.resource} = {self.limit_value}"


class QuotaOverride(models.Model):
    """A special limit for one user that replaces their tier's limit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resource = models.CharField(max_length=64)
    limit_value = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "resource"], name="one_override_per_user_and_resource"
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.resource} = {self.limit_value}"


class QuotaUsage(models.Model):
    """How much of a daily limit a user has used on one day.

    "scope" separates counters for limits that apply to one item, for
    example one plan's posts per day. It is empty for account-wide limits.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resource = models.CharField(max_length=64)
    scope = models.CharField(max_length=64, blank=True, default="")
    day = models.DateField()
    used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "resource", "scope", "day"],
                name="one_usage_row_per_user_resource_scope_and_day",
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.resource} on {self.day} = {self.used}"
