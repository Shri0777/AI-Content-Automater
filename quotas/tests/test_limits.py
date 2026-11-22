"""Tests for looking up limits and checking "at any time" limits."""

import pytest
from django.contrib.auth import get_user_model

from quotas.models import QuotaOverride
from quotas.services import (
    QuotaExceeded,
    UnknownQuotaResource,
    check_count_allowed,
    check_total_limit,
    get_limit,
)


@pytest.fixture
def user(db):
    """A saved user on the free tier."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


def test_free_tier_limits_come_from_the_database(user):
    assert get_limit(user, "active_plans") == 3
    assert get_limit(user, "posts_per_day") == 10
    assert get_limit(user, "posts_per_plan_per_day") == 10
    assert get_limit(user, "generate_now_per_day") == 10


def test_an_override_beats_the_tier_limit(user):
    QuotaOverride.objects.create(user=user, resource="active_plans", limit_value=10)

    assert get_limit(user, "active_plans") == 10


def test_an_unknown_resource_is_a_programming_error(user):
    with pytest.raises(UnknownQuotaResource):
        get_limit(user, "rockets_per_day")


def test_total_limit_allows_counts_below_the_limit(user):
    check_total_limit(user, "active_plans", current_count=2)


def test_total_limit_refuses_when_the_limit_is_already_reached(user):
    with pytest.raises(QuotaExceeded) as error:
        check_total_limit(user, "active_plans", current_count=3)

    assert error.value.extra["resource"] == "active_plans"
    assert error.value.extra["limit"] == 3
    assert "3" in error.value.detail


def test_creating_exactly_the_limit_at_once_is_allowed(user):
    check_count_allowed(user, "topics_per_plan", wanted_count=6)


def test_creating_more_than_the_limit_at_once_is_refused(user):
    with pytest.raises(QuotaExceeded):
        check_count_allowed(user, "topics_per_plan", wanted_count=7)
