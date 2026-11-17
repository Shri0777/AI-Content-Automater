"""Reading real-shaped sources politely: budgets, caching, robots.txt, SSRF."""

import pytest
from django.contrib.auth import get_user_model

from core import web
from core.errors import ProviderError
from newsroom.budgets import requests_used_today
from newsroom.fetching import get_with_redirects
from newsroom.ingest import ingest_active_presets, ingest_preset
from newsroom.models import Article
from newsroom.presets import TOPIC_PRESETS
from planning.models import ContentPlan, Topic
from tests.news_stubs import (
    ALLOW_ALL_ROBOTS,
    ARTICLE_PAGE,
    BLOCK_AI_ROBOTS,
    hackernews_answer,
    rss_feed,
)


@pytest.fixture
def news_site(db, stub_server, settings, monkeypatch):
    """A stub news site with a feed, an article page and a search API."""
    settings.DEMO_MODE = False
    settings.HACKERNEWS_SEARCH_URL = f"{stub_server.base_url}/hn"
    base = stub_server.base_url
    feed = {"body": rss_feed(base), "headers": {"ETag": '"v1"'}}
    stub_server.set_route("GET", "/feed.xml", feed)
    stub_server.set_route("GET", "/robots.txt", {"body": ALLOW_ALL_ROBOTS})
    stub_server.set_route("GET", "/articles/2", {"body": ARTICLE_PAGE})
    stub_server.set_route("GET", "/hn", {"body": hackernews_answer(base)})
    stub_server.set_route("GET", "/hn-story", {"body": ARTICLE_PAGE})
    sources = [
        {
            "type": "rss",
            "name": "Example",
            "url": f"{base}/feed.xml",
            "tier": "reputable",
        },
        {
            "type": "hackernews",
            "name": "Hacker News",
            "query": "AI",
            "tier": "aggregator",
        },
    ]
    monkeypatch.setitem(TOPIC_PRESETS["ai_news"], "sources", sources)
    return stub_server


def test_feed_items_are_stored_and_short_ones_get_their_page_read(news_site):
    assert ingest_preset("ai_news") == 3

    from_feed = Article.objects.get(title="New open model beats the old one")
    from_page = Article.objects.get(title="Short item that needs its page read")
    assert from_feed.text_source == "feed"
    assert from_page.text_source == "page"
    assert "Home | News" not in from_page.text


def test_hacker_news_stories_are_credited_to_the_linked_site(news_site):
    ingest_preset("ai_news")

    story = Article.objects.get(title="Company lays off 200 engineers")
    assert story.source_name == "127.0.0.1"
    assert story.source_tier == "aggregator"
    assert story.popularity == 120
    search = news_site.requests_to("/hn")[0]["query"]
    assert search["tags"] == "story"
    assert not Article.objects.filter(title__startswith="Ask HN").exists()


def test_an_unchanged_feed_is_asked_only_if_changed(news_site):
    ingest_preset("ai_news")
    news_site.set_route("GET", "/feed.xml", {"status": 304, "body": b""})

    ingest_preset("ai_news")

    second_read = news_site.requests_to("/feed.xml")[1]
    assert second_read["headers"]["If-None-Match"] == '"v1"'
    assert Article.objects.count() == 3


def test_pages_are_not_read_where_robots_txt_blocks_ai_crawlers(news_site):
    news_site.set_route("GET", "/robots.txt", {"body": BLOCK_AI_ROBOTS})

    ingest_preset("ai_news")

    assert news_site.requests_to("/articles/2") == []
    short = Article.objects.get(title="Short item that needs its page read")
    assert short.text_source == "feed"
    assert short.page_checked is True


def test_every_request_says_who_is_reading(news_site, settings):
    ingest_preset("ai_news")

    for request in news_site.requests:
        assert request["headers"]["User-Agent"] == settings.NEWS_USER_AGENT


def test_a_source_over_its_daily_cap_is_not_read_and_stored_articles_remain(
    news_site, settings
):
    ingest_preset("ai_news")
    stored = Article.objects.count()
    settings.NEWS_DAILY_REQUEST_CAPS = {"rss": 1, "hackernews": 1, "pages": 1}
    feed_reads = len(news_site.requests_to("/feed.xml"))

    ingest_preset("ai_news")

    assert len(news_site.requests_to("/feed.xml")) == feed_reads
    assert requests_used_today("rss") == 1
    assert Article.objects.count() == stored


def test_the_same_story_from_another_outlet_is_stored_once(news_site):
    ingest_preset("ai_news")
    copy_feed = rss_feed(f"{news_site.base_url}/copy")
    news_site.set_route("GET", "/feed.xml", {"body": copy_feed})

    ingest_preset("ai_news")

    assert Article.objects.filter(title="New open model beats the old one").count() == 1


def test_only_presets_that_active_plans_follow_are_read(news_site):
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    active = ContentPlan.objects.create(user=user, name="Active")
    paused = ContentPlan.objects.create(user=user, name="Paused", paused=True)
    Topic.objects.create(plan=active, name="AI", preset="ai_news")
    Topic.objects.create(plan=paused, name="Layoffs", preset="layoffs")

    ingest_active_presets()

    assert set(Article.objects.values_list("preset", flat=True)) == {"ai_news"}


def test_a_redirect_to_a_private_address_is_refused(db, monkeypatch, settings):
    settings.ALLOW_PRIVATE_PROVIDER_URLS = False
    real_send = web.send

    def redirect_inwards(method, url, headers, payload=None):
        if url == "https://news.example.com/feed":
            raise web.Redirected("moved", "https://169.254.169.254/latest/meta-data")
        return real_send(method, url, headers, payload)

    monkeypatch.setattr(web, "send", redirect_inwards)

    with pytest.raises(ProviderError, match="private network"):
        get_with_redirects("https://news.example.com/feed", {}, "rss")


def test_a_broad_feed_keeps_only_items_about_the_topic(news_site, monkeypatch):
    base = news_site.base_url
    broad = {"type": "rss", "name": "Wide", "url": f"{base}/feed.xml"}
    broad["tier"] = "reputable"
    broad["broad"] = True
    monkeypatch.setitem(TOPIC_PRESETS["layoffs"], "sources", [broad])

    ingest_preset("layoffs")

    # Neither feed item mentions layoffs, so nothing is stored for the topic.
    assert not Article.objects.filter(preset="layoffs").exists()


def test_a_feed_shared_by_two_presets_gives_each_its_new_items(news_site, monkeypatch):
    shared = {"type": "rss", "name": "Shared", "tier": "reputable"}
    shared["url"] = f"{news_site.base_url}/feed.xml"
    monkeypatch.setitem(TOPIC_PRESETS["ai_news"], "sources", [shared])
    monkeypatch.setitem(TOPIC_PRESETS["linux_tips"], "sources", [shared])

    ingest_preset("ai_news")
    ingest_preset("linux_tips")

    reads = news_site.requests_to("/feed.xml")
    assert "If-None-Match" not in reads[1]["headers"]
    assert Article.objects.filter(preset="linux_tips").count() == 2
