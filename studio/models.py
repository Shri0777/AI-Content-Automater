"""Database tables for posts and everything made while generating them.

Post            - one post for one plan, moving through STATUS_CHOICES
PostVersion     - the words and poster of a post (filled in by the
                  pipeline stages, then never changed)
Review          - the AI review of one version, with a verdict
GenerationStep  - one row per pipeline stage run: the audit trail
"""

import uuid

from django.conf import settings
from django.db import models

from studio.verdicts import total_score

# The allowed changes between these are in studio/statuses.py.
STATUS_CHOICES = [
    ("researching", "Finding an article"),
    ("drafting", "Writing the caption"),
    ("imaging", "Making the poster"),
    ("reviewing", "Checking the post"),
    ("correcting", "Fixing what the review found"),
    ("awaiting_approval", "Waiting for your approval"),
    ("approved", "Approved"),
    ("publishing", "Publishing"),
    ("published", "Published"),
    ("rejected", "Rejected"),
    ("expired", "Expired before it was approved"),
    ("skipped", "Skipped"),
    ("failed", "Failed"),
]

VERDICT_CHOICES = [
    ("pass", "Pass"),
    ("revise", "Needs changes"),
    ("reject", "Reject"),
]


class Post(models.Model):
    """One post being made for a plan, from research to publishing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(
        "planning.ContentPlan", on_delete=models.CASCADE, related_name="posts"
    )
    topic = models.ForeignKey(
        "planning.Topic", on_delete=models.SET_NULL, null=True, related_name="posts"
    )
    article = models.ForeignKey(
        "newsroom.Article", on_delete=models.SET_NULL, null=True, blank=True
    )
    # The schedule slot this post was made for; empty for "generate now".
    slot = models.OneToOneField(
        "planning.PostSlot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="researching"
    )
    # Why the post was skipped or failed, in plain words.
    status_reason = models.TextField(blank=True)
    # True when the post was made by the built-in fake providers.
    demo_mode = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"Post {self.id} ({self.status})"

    def latest_version(self):
        """Return the newest PostVersion, or None if nothing is written yet."""
        return self.versions.order_by("-number").first()

    def final_version(self):
        """Return the version to show and publish: the best-reviewed one.

        A correction can come out worse than the version before it; then the
        earlier, better one is used. Ties go to the newest version. A version
        the user edited themselves always wins: it is their decision.
        """
        edited = self.versions.filter(edited_by_user=True).order_by("-number").first()
        if edited is not None:
            return edited
        totals = {}
        for review in Review.objects.filter(version__post=self):
            totals[review.version_id] = review.total()
        best = None
        best_total = -1
        for version in self.versions.order_by("number"):
            total = totals.get(version.id, 0)
            if total >= best_total:
                best = version
                best_total = total
        return best


class PostVersion(models.Model):
    """The headline, caption and poster of one version of a post."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    headline = models.CharField(max_length=200)
    caption = models.TextField()
    image_prompt = models.TextField(blank=True)
    # The AI artwork without text, kept so a corrected headline can be put
    # on the same artwork without paying for a new image.
    artwork_path = models.CharField(max_length=300, blank=True)
    # True when the user wrote this version themselves (edited the caption).
    edited_by_user = models.BooleanField(default=False)
    # True once the poster and artwork files were deleted after the
    # retention period (the words and the history are kept).
    image_expired = models.BooleanField(default=False)
    # Where the poster image is saved in file storage ("" until it exists).
    poster_path = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "number"], name="one_version_number_per_post"
            )
        ]

    def __str__(self):
        return f"{self.post} v{self.number}"


class Review(models.Model):
    """The AI review of one version and the verdict worked out from it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField(
        PostVersion, on_delete=models.CASCADE, related_name="review"
    )
    # For example {"grounding": 5, "clarity": 4}, each from 1 to 5.
    scores = models.JSONField()
    # A list of {"severity", "problem", "fix_instruction"} dicts.
    issues = models.JSONField(default=list)
    verdict = models.CharField(max_length=10, choices=VERDICT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review of {self.version}: {self.verdict}"

    def total(self):
        """Return the sum of the five scores, for comparing versions."""
        return total_score(self.scores)


class GenerationStep(models.Model):
    """A record of one pipeline stage run, kept for debugging."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="steps")
    stage = models.CharField(max_length=20)
    succeeded = models.BooleanField()
    duration_ms = models.PositiveIntegerField()
    error = models.TextField(blank=True)
    # Which models were used, for example "anthropic:claude-opus-5-5".
    providers = models.CharField(max_length=300, blank=True)
    # Which prompt wordings were used (see studio/prompts.py).
    prompt_versions = models.CharField(max_length=200, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.post}: {self.stage}"
