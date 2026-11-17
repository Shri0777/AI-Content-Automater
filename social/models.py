"""Database table for the social media accounts a user has linked.

Posts are published to these accounts. Tokens from the platform are stored
encrypted (see core/crypto.py) and are never sent back by the API.
"""

import uuid

from django.conf import settings
from django.db import models

PLATFORM_CHOICES = [
    ("demo", "Demo network"),
    ("buffer", "Buffer"),
    ("x", "X"),
    ("linkedin", "LinkedIn"),
    ("facebook", "Facebook Page"),
]

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
    # Where the posts really appear. Usually the same as platform; for a
    # Buffer channel it is the network Buffer posts to, for example "linkedin".
    network = models.CharField(max_length=30, blank=True)
    encrypted_token = models.TextField(blank=True)
    encrypted_refresh_token = models.TextField(blank=True)
    # When the access token stops working. Empty means it does not expire.
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    # Why the account needs attention, in plain words.
    last_error = models.TextField(blank=True)
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


class LinkAttempt(models.Model):
    """One "connect my account" attempt that is waiting for the platform.

    The platform sends the user back with the same random state text we gave
    it. We store only the state's SHA-256 fingerprint, and each attempt can be
    finished once, so a stolen or replayed link cannot connect an account.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    state_hash = models.CharField(max_length=64, unique=True)
    # The PKCE secret (see social/oauth.py), encrypted like every token.
    encrypted_code_verifier = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.platform} link for {self.user}"
