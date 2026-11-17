"""Tests for daily limits, which start again at midnight in the user's timezone."""

import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from freezegun import freeze_time

from quotas.models import QuotaUsage
from quotas.services import QuotaExceeded, get_daily_used, use_daily_quota


@pytest.fixture
def user(db):
    """A saved user on the free tier (6 posts per day)."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


def use_posts(user, how_many):
    """Use up some of today's post allowance."""
    for _ in range(how_many):
        use_daily_quota(user, "posts_per_day")


def test_each_use_is_counted(user):
    use_posts(user, 2)

    assert get_daily_used(user, "posts_per_day") == 2


def test_the_seventh_post_of_the_day_is_refused(user):
    use_posts(user, 6)

    with pytest.raises(QuotaExceeded) as error:
        use_daily_quota(user, "posts_per_day")

    assert error.value.code == "quota_exceeded"
    assert error.value.extra["limit"] == 6
    assert error.value.extra["used"] == 6
    assert get_daily_used(user, "posts_per_day") == 6


def test_the_limit_starts_again_the_next_day(user):
    with freeze_time("2026-11-12 10:00:00"):
        use_posts(user, 6)

    with freeze_time("2026-11-13 00:01:00"):
        use_daily_quota(user, "posts_per_day")

        assert get_daily_used(user, "posts_per_day") == 1


def test_the_day_follows_the_users_own_timezone(user):
    user.timezone = "Asia/Kolkata"
    user.save()

    # 19:00 in London on 12 November is already 00:30 on 13 November in India.
    with freeze_time("2026-11-12 19:00:00"):
        use_daily_quota(user, "posts_per_day")

    assert QuotaUsage.objects.get().day.isoformat() == "2026-11-13"


def test_the_error_says_when_the_limit_starts_again(user):
    user.timezone = "Asia/Kolkata"
    user.save()

    with freeze_time("2026-11-12 10:00:00"):
        use_posts(user, 6)
        with pytest.raises(QuotaExceeded) as error:
            use_daily_quota(user, "posts_per_day")

    assert error.value.extra["resets_at"] == "2026-11-13T00:00:00+05:30"


def test_separate_scopes_have_separate_counters(user):
    for _ in range(4):
        use_daily_quota(user, "posts_per_plan_per_day", scope="plan-a")

    use_daily_quota(user, "posts_per_plan_per_day", scope="plan-b")

    assert get_daily_used(user, "posts_per_plan_per_day", scope="plan-b") == 1


def try_to_use_one_post(user, successes):
    """Use one post from a separate thread, like a separate web request."""
    try:
        use_daily_quota(user, "posts_per_day")
        successes.append(True)
    except QuotaExceeded:
        pass
    finally:
        # Each thread opens its own database connection; close it when done.
        connection.close()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_many_requests_at_the_same_moment_never_go_over_the_limit():
    user = get_user_model().objects.create_user(
        email="racer@example.com", password="correct-horse-battery-staple"
    )
    successes = []

    threads = []
    for _ in range(20):
        thread = threading.Thread(target=try_to_use_one_post, args=(user, successes))
        threads.append(thread)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 6
    assert get_daily_used(user, "posts_per_day") == 6
