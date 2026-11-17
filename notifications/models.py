"""Database table for in-app notifications (the only way we contact users)."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

# Every kind of notification, with the title users see.
KIND_CHOICES = [
    ("post_awaiting_approval", "A post is waiting for your approval"),
    ("post_published", "Post published"),
    ("publish_unconfirmed", "Check whether a post went out"),
    ("post_failed", "A post could not be made"),
    ("post_skipped", "A post was skipped"),
    ("post_expired", "A post expired before it was approved"),
    ("account_needs_reauth", "Reconnect a social account"),
    ("credential_invalid", "An API key stopped working"),
    ("quota_reached", "You reached a free-tier limit"),
    ("plan_paused", "A content plan was paused"),
    ("outage_missed_slots", "Some scheduled posts were missed"),
]


class Notification(models.Model):
    """One message shown to a user inside the app."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    # What the notification is about, for example a post. Optional.
    related_type = models.CharField(max_length=40, blank=True)
    related_id = models.UUIDField(null=True, blank=True)
    # Notifications with the same key are collapsed while one is unread.
    dedupe_key = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.user}: {self.title}"

    def mark_as_read(self):
        """Record that the user has seen this notification."""
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])
