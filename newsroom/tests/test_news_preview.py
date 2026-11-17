"""Previewing the articles a topic would use, through the API."""

import pytest
from django.contrib.auth import get_user_model

from quotas.models import QuotaOverride

URL = "/api/v1/news/preview/"


@pytest.fixture
def user(db):
    """The logged-in user."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


@pytest.fixture
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client


def test_a_preview_needs_a_login(api_client, db):
    assert api_client.get(URL, {"preset": "ai_news"}).status_code == 401


def test_a_preview_lists_the_best_stored_articles(client):
    response = client.get(URL, {"preset": "ai_news"})

    assert response.status_code == 200
    articles = response.json()
    assert 1 <= len(articles) <= 5
    assert set(articles[0]) == {
        "title",
        "url",
        "source_name",
        "source_tier",
        "published_at",
        "text_source",
    }


def test_an_unknown_preset_is_refused(client):
    response = client.get(URL, {"preset": "gossip"})

    assert response.status_code == 400
    assert response.json()["code"] == "unknown_preset"


def test_previews_count_towards_the_daily_limit(client, user):
    QuotaOverride.objects.create(
        user=user, resource="news_previews_per_day", limit_value=1
    )

    first = client.get(URL, {"preset": "ai_news"})
    second = client.get(URL, {"preset": "ai_news"})

    assert first.status_code == 200
    assert second.status_code == 403
