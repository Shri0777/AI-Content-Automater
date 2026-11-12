"""Tests for choosing a news article for a plan's topic."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.errors import ProviderError
from demo.news_source import DemoNewsSource
from newsroom.models import Article
from newsroom.services import pick_article, record_article_use
from planning.models import ContentPlan


@pytest.fixture
def plan(db):
    """A saved plan belonging to a new user."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    return ContentPlan.objects.create(user=user, name="Tech news")


def test_the_newest_article_for_the_preset_is_picked(plan):
    article = pick_article(plan, "ai_news")

    assert article.preset == "ai_news"
    assert article.title.startswith("Woodgrove Labs")


def test_a_plan_never_gets_the_same_article_twice(plan):
    titles = []
    for _ in range(3):
        article = pick_article(plan, "ai_news")
        record_article_use(plan, article)
        titles.append(article.title)

    assert len(set(titles)) == 3
    assert pick_article(plan, "ai_news") is None


def test_articles_are_stored_once_however_often_sources_are_read(plan):
    pick_article(plan, "layoffs")
    pick_article(plan, "layoffs")

    assert Article.objects.filter(preset="layoffs").count() == 3


def test_old_news_is_not_used(plan, monkeypatch):
    two_weeks_ago = timezone.now() - timedelta(days=14)
    monkeypatch.setattr("newsroom.services.get_news_sources", list)
    Article.objects.create(
        url_hash="old",
        url="https://example.com/old",
        title="Old story",
        source_name="Demo",
        preset="ai_news",
        published_at=two_weeks_ago,
    )

    assert pick_article(plan, "ai_news") is None


def test_evergreen_tips_never_go_stale(plan, monkeypatch):
    two_years_ago = timezone.now() - timedelta(days=730)
    monkeypatch.setattr("newsroom.services.get_news_sources", list)
    Article.objects.create(
        url_hash="tip",
        url="https://example.com/tip",
        title="An old but useful tip",
        source_name="Demo",
        preset="linux_tips",
        published_at=two_years_ago,
    )

    assert pick_article(plan, "linux_tips").title == "An old but useful tip"


def test_no_sources_are_read_outside_demo_mode_yet(plan, settings):
    settings.DEMO_MODE = False

    assert pick_article(plan, "ai_news") is None


class BrokenSource(DemoNewsSource):
    """A source that is always down."""

    def fetch_articles(self, preset):
        raise ProviderError("The source is down.")


def test_a_failing_source_is_skipped(plan, monkeypatch):
    def broken_then_working():
        return [BrokenSource(), DemoNewsSource()]

    monkeypatch.setattr("newsroom.services.get_news_sources", broken_then_working)

    assert pick_article(plan, "ai_news") is not None
