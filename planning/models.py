"""Database tables for content plans and the topics they follow.

A plan says what to post about (its topics and free-text requirements),
where to post (linked social accounts) and how posts are approved.
Schedules (days and times) arrive in Phase 5; for now posts are made with
"generate now".
"""

import uuid

from django.conf import settings
from django.db import models

from newsroom.presets import PRESET_CHOICES

# Automatic posting arrives in Phase 8 with the auto-post gate. Until then
# every post waits for the user's approval.
APPROVAL_MODE_CHOICES = [
    ("manual", "I approve every post"),
]

DEFAULT_AI_LABEL = "Made with AI assistance."


class ContentPlan(models.Model):
    """What to post about, where, and how posts are approved."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    # Free text that guides which news is chosen and how posts are written.
    requirements = models.TextField(blank=True)
    approval_mode = models.CharField(
        max_length=20, choices=APPROVAL_MODE_CHOICES, default="manual"
    )
    accounts = models.ManyToManyField("social.SocialAccount", blank=True)
    ai_label_enabled = models.BooleanField(default=True)
    ai_label_text = models.CharField(max_length=100, default=DEFAULT_AI_LABEL)
    paused = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.name


class Topic(models.Model):
    """One subject a plan posts about, for example "AI news"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        ContentPlan, on_delete=models.CASCADE, related_name="topics"
    )
    name = models.CharField(max_length=100)
    preset = models.CharField(max_length=40, choices=PRESET_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.plan}: {self.name}"
