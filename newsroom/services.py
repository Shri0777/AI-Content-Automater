"""Read articles from news sources and choose one for a plan's topic.

For now, sources are read at the moment a post needs an article. Phase 6
moves this to a shared background job with per-source daily budgets.
"""

import hashlib
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.errors import ProviderError
from demo.news_source import DemoNewsSource
from newsroom.models import Article, ArticleUse
from newsroom.presets import TOPIC_PRESETS


def get_news_sources():
    """Return the news sources to read. Real ones are added in Phase 6."""
    if settings.DEMO_MODE:
        return [DemoNewsSource()]
    return []


def url_fingerprint(url):
    """Return a short fixed-length fingerprint of an article's address."""
    return hashlib.sha256(url.encode()).hexdigest()


def save_articles(preset, items):
    """Store articles from a source; one already stored is updated."""
    for item in items:
        Article.objects.update_or_create(
            url_hash=url_fingerprint(item["url"]),
            defaults={
                "url": item["url"],
                "title": item["title"],
                "source_name": item["source_name"],
                "preset": preset,
                "published_at": item["published_at"],
                "text": item["text"],
            },
        )


def read_sources(preset):
    """Read every source for a preset. A failing source is skipped."""
    for source in get_news_sources():
        try:
            items = source.fetch_articles(preset)
        except ProviderError:
            continue
        save_articles(preset, items)


def pick_article(plan, preset):
    """Return the newest article for preset the plan has not used, or None.

    News topics only consider articles within the preset's freshness window.
    """
    read_sources(preset)
    candidates = Article.objects.filter(preset=preset).exclude(
        id__in=ArticleUse.objects.filter(plan=plan).values("article_id")
    )
    freshness_hours = TOPIC_PRESETS[preset]["freshness_hours"]
    if freshness_hours > 0:
        oldest_allowed = timezone.now() - timedelta(hours=freshness_hours)
        candidates = candidates.filter(published_at__gte=oldest_allowed)
    return candidates.order_by("-published_at").first()


def record_article_use(plan, article):
    """Remember that plan used article, so it is not picked again."""
    ArticleUse.objects.get_or_create(plan=plan, article=article)
