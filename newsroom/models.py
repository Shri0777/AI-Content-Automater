"""Database tables for news articles and which plans have used them.

Articles are shared: one copy is stored no matter how many users follow the
same topic. ArticleUse remembers which plan used which article, so a plan
never posts about the same story twice.
"""

import uuid

from django.db import models

from newsroom.presets import PRESET_CHOICES


class Article(models.Model):
    """One news article (or evergreen tip) read from a news source."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # A fingerprint of the address, so each article is stored only once.
    url_hash = models.CharField(max_length=64, unique=True)
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500)
    source_name = models.CharField(max_length=200)
    preset = models.CharField(max_length=40, choices=PRESET_CHOICES)
    published_at = models.DateTimeField()
    text = models.TextField(blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["preset", "published_at"])]

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
