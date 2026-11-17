"""Database table for each time a post is sent to a social account."""

import uuid

from django.db import models

STATUS_CHOICES = [
    ("publishing", "Publishing"),
    ("published", "Published"),
    ("failed", "Failed"),
    # Sent, but the platform never answered: it may or may not be posted.
    # Never sent again automatically; reconcile or the user settles it.
    ("ambiguous", "Not confirmed"),
]

RESOLVED_BY_CHOICES = [
    ("", "Not settled"),
    ("platform", "Checked with the platform"),
    ("user", "Confirmed by the user"),
]


class Publication(models.Model):
    """One post version sent (or being sent) to one social account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        "studio.Post", on_delete=models.CASCADE, related_name="publications"
    )
    version = models.ForeignKey("studio.PostVersion", on_delete=models.CASCADE)
    # Kept when the account is unlinked later, so the history stays.
    account = models.ForeignKey(
        "social.SocialAccount", on_delete=models.SET_NULL, null=True
    )
    # The same post, version and account always get the same key, and the
    # key is unique, so the same thing can never be published twice.
    idempotency_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="publishing"
    )
    # The post's id on the platform, once it is published.
    external_id = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)
    demo_mode = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # For an "ambiguous" publication: when it was last checked, and who
    # settled it in the end.
    checked_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(
        max_length=10, choices=RESOLVED_BY_CHOICES, blank=True
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.post} to {self.account} ({self.status})"

    def account_name(self):
        """Return the account's name, even after it was unlinked."""
        if self.account is None:
            return "an account you have since removed"
        return self.account.display_name
