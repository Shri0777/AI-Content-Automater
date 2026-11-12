"""Database table for the social media accounts a user has linked.

Posts are published to these accounts. Tokens from the platform are stored
encrypted (see core/crypto.py) and are never sent back by the API.
"""

import uuid

from django.conf import settings
from django.db import models

# Real platforms (Buffer, LinkedIn, X, Meta) are added in Phase 4.
PLATFORM_CHOICES = [
    ("demo", "Demo network"),
]

# The longest caption each platform accepts, in characters.
CAPTION_LIMITS = {
    "demo": 3000,
}

STATUS_CHOICES = [
    ("active", "Active"),
    ("needs_reauth", "Needs to be reconnected"),
    ("revoked", "Revoked"),
]


class SocialAccount(models.Model):
    """One linked account on a social media platform."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    # The name users recognise, for example "Ada's LinkedIn page".
    display_name = models.CharField(max_length=200)
    # The account's id on the platform itself.
    external_id = models.CharField(max_length=200)
    encrypted_token = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform", "external_id"],
                name="one_link_per_platform_account",
            )
        ]

    def __str__(self):
        return f"{self.display_name} ({self.platform})"
