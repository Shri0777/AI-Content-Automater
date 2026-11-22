"""Database tables for news articles, the feeds they come from and budgets.

Articles are shared: one copy is stored no matter how many users follow the
same topic. ArticleUse remembers which plan used which article, so a plan
never posts about the same story twice. FeedState and SourceBudget keep the
reading polite: feeds are asked "only if changed", and each kind of source
has a daily request cap.
"""

import uuid

from django.db import models
from django.utils import timezone


class Article(models.Model):
    """One news article (or evergreen tip) read from a news source."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # A fingerprint of the address. Each article is stored once per preset
    # (a story can be about layoffs and AI at the same time).
    url_hash = models.CharField(max_length=64)
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500)
    # The title in lower case without punctuation, to spot the same story
    # published by several outlets.
    title_key = models.CharField(max_length=500, blank=True, db_index=True)
    source_name = models.CharField(max_length=200)
    # How much the source is trusted: "primary", "reputable" or "aggregator".
    source_tier = models.CharField(max_length=20, default="reputable")
    # Votes or similar from the source (Hacker News points); 0 if none.
    popularity = models.PositiveIntegerField(default=0)
    # A built-in preset key, or "custom-<topic id>" for a user's own topic.
    preset = models.CharField(max_length=40)
    published_at = models.DateTimeField()
    text = models.TextField(blank=True)
    # Where the text came from: "feed", "page" (fetched and cleaned) or "".
    text_source = models.CharField(max_length=10, blank=True)
    # True once we tried to fetch the page, so it is never fetched twice.
    page_checked = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(auto_now=True)
    # True for the canned, fictional demo articles. Demo mode only uses demo
    # articles and live mode never does, so the two can never mix.
    is_demo = models.BooleanField(default=False)
    # When the article was first stored; retention counts from here.
    stored_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["preset", "published_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["url_hash", "preset"], name="one_article_per_preset"
            )
        ]

    def __str__(self):
        return self.title


class ArticleUse(models.Model):
    """A record that one plan has used one article."""

    plan = models.ForeignKey("planning.ContentPlan", on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "article"], name="plan_uses_article_once"
            )
        ]

    def __str__(self):
        return f"{self.plan} used {self.article}"


class FeedState(models.Model):
    """What a feed told us last time, so we can ask "only if it changed".

    Kept per preset: one feed can serve two presets, and each must see every
    new item once, so "unchanged since my last read" is per preset.
    """

    url = models.URLField(max_length=1000)
    preset = models.CharField(max_length=40)
    etag = models.CharField(max_length=300, blank=True)
    last_modified = models.CharField(max_length=100, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["url", "preset"], name="one_state_per_feed")
        ]

    def __str__(self):
        return f"{self.url} ({self.preset})"


class SourceBudget(models.Model):
    """How many requests one kind of source has used on one day (UTC)."""

    source = models.CharField(max_length=40)
    day = models.DateField()
    used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "day"], name="one_budget_per_day")
        ]

    def __str__(self):
        return f"{self.source} on {self.day}: {self.used}"


class IngestRecord(models.Model):
    """When a topic preset's sources were last read."""

    preset = models.CharField(max_length=40, unique=True)
    finished_at = models.DateTimeField()

    def __str__(self):
        return f"{self.preset} at {self.finished_at}"
