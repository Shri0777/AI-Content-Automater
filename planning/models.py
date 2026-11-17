"""Database tables for content plans, their topics and their schedules.

A plan says what to post about (its topics and free-text requirements),
where to post (linked social accounts), how posts are approved and when to
post (schedule rules). Each rule is turned into PostSlot rows, one per
planned post, by planning/schedule.py; planning/dispatcher.py starts them.
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

# What happens to a post still waiting for approval when its time has passed.
ON_MISSED_APPROVAL_CHOICES = [
    ("expire", "Drop it (old news loses its value)"),
    ("hold", "Keep it; publish as soon as I approve"),
]


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
    # How long before the posting time a post starts being made. It leaves
    # time to approve it, so it is longer than the making itself needs.
    lead_time_minutes = models.PositiveIntegerField(default=60)
    # A post that cannot start within this long after its time is skipped,
    # for example after the server was down, instead of posting stale news.
    max_lateness_minutes = models.PositiveIntegerField(default=30)
    on_missed_approval = models.CharField(
        max_length=10, choices=ON_MISSED_APPROVAL_CHOICES, default="expire"
    )
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


class ScheduleRule(models.Model):
    """When a plan posts: some weekdays, at some local times, in one timezone.

    Times are kept in local time with the timezone's name (for example
    "Asia/Kolkata"), so 09:00 stays 09:00 when the clocks change.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        ContentPlan, on_delete=models.CASCADE, related_name="schedule_rules"
    )
    # Weekday numbers, Monday = 0 ... Sunday = 6, for example [0, 2, 4].
    days_of_week = models.JSONField()
    # Local times as "HH:MM" text, for example ["09:00", "18:30"].
    times = models.JSONField()
    timezone = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.plan}: {self.days_of_week} at {self.times} ({self.timezone})"


SLOT_STATUS_CHOICES = [
    ("waiting", "Waiting for its time"),
    ("claimed", "Being started by a worker"),
    ("started", "Post started"),
    ("skipped", "Skipped"),
]


class PostSlot(models.Model):
    """One planned post: when it is published and when making it starts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        ContentPlan, on_delete=models.CASCADE, related_name="slots"
    )
    rule = models.ForeignKey(ScheduleRule, on_delete=models.SET_NULL, null=True)
    publish_at = models.DateTimeField()
    generate_at = models.DateTimeField()
    status = models.CharField(
        max_length=10, choices=SLOT_STATUS_CHOICES, default="waiting"
    )
    # A worker that claims a slot holds it until this time. If the worker
    # crashes, the claim runs out and another worker can start the slot.
    claimed_until = models.DateTimeField(null=True, blank=True)
    skip_reason = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["publish_at"]
        constraints = [
            # Making slots twice can never create the same slot twice.
            models.UniqueConstraint(
                fields=["plan", "publish_at"], name="one_slot_per_plan_and_time"
            )
        ]
        indexes = [models.Index(fields=["status", "generate_at"])]

    def __str__(self):
        return f"{self.plan} at {self.publish_at} ({self.status})"
