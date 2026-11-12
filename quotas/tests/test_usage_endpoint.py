"""Tests for /api/v1/me/usage/, which shows every limit and how much is used."""

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from quotas.services import use_daily_quota

USAGE_URL = "/api/v1/me/usage/"


@pytest.fixture
def user(db):
    """A saved user on the free tier."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


def find_limit(response, resource):
    """Return the entry for one resource from the usage response."""
    for item in response.json()["limits"]:
        if item["resource"] == resource:
            return item
    return None


def test_usage_needs_a_login(api_client, db):
    response = api_client.get(USAGE_URL)

    assert response.status_code == 401


def test_usage_lists_the_users_tier_and_limits(api_client, user):
    api_client.force_authenticate(user)

    response = api_client.get(USAGE_URL)

    assert response.status_code == 200
    assert response.json()["tier"] == "free"
    assert find_limit(response, "active_plans")["limit"] == 3


@freeze_time("2026-11-12 10:00:00")
def test_daily_usage_shows_what_is_used_and_when_it_resets(api_client, user):
    use_daily_quota(user, "posts_per_day")
    use_daily_quota(user, "posts_per_day")
    api_client.force_authenticate(user)

    posts = find_limit(api_client.get(USAGE_URL), "posts_per_day")

    assert posts["used"] == 2
    assert posts["limit"] == 6
    assert posts["resets_at"] == "2026-11-13T00:00:00+00:00"


def test_limits_for_each_plan_have_no_account_wide_usage(api_client, user):
    api_client.force_authenticate(user)

    topics = find_limit(api_client.get(USAGE_URL), "topics_per_plan")

    assert topics["applies_to"] == "plan"
    assert topics["used"] is None
