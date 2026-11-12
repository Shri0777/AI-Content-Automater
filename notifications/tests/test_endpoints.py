"""Tests for the notification endpoints the frontend polls."""

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from notifications.models import Notification
from notifications.services import notify

LIST_URL = "/api/v1/notifications/"
COUNT_URL = "/api/v1/notifications/unread-count/"
READ_ALL_URL = "/api/v1/notifications/read-all/"


def make_user(email):
    """Create and return a saved user."""
    return get_user_model().objects.create_user(
        email=email, password="correct-horse-battery-staple"
    )


@pytest.fixture
def user(db):
    """The logged-in user in these tests."""
    return make_user("ada@example.com")


@pytest.fixture
def other_user(db):
    """Somebody else, whose notifications must stay private."""
    return make_user("grace@example.com")


def test_the_list_needs_a_login(api_client, db):
    assert api_client.get(LIST_URL).status_code == 401


def test_users_see_only_their_own_notifications_newest_first(
    api_client, user, other_user
):
    with freeze_time("2026-11-12 09:00"):
        notify(user, "post_published", "First.")
    with freeze_time("2026-11-12 10:00"):
        notify(user, "post_published", "Second.")
    notify(other_user, "post_published", "Not yours.")
    api_client.force_authenticate(user)

    results = api_client.get(LIST_URL).json()["results"]

    messages = [item["message"] for item in results]
    assert messages == ["Second.", "First."]


def test_the_list_can_show_only_unread_notifications(api_client, user):
    first = notify(user, "post_published", "Already seen.")
    first.mark_as_read()
    notify(user, "post_published", "New.")
    api_client.force_authenticate(user)

    results = api_client.get(LIST_URL + "?unread=true").json()["results"]

    assert len(results) == 1
    assert results[0]["message"] == "New."


def test_long_lists_come_in_pages_of_twenty(api_client, user):
    for number in range(25):
        notify(user, "post_published", f"Post {number}.")
    api_client.force_authenticate(user)

    first_page = api_client.get(LIST_URL).json()

    assert len(first_page["results"]) == 20
    assert first_page["next"] is not None


def test_unread_count_counts_only_unread(api_client, user):
    notify(user, "post_published", "One.")
    notify(user, "post_published", "Two.").mark_as_read()
    api_client.force_authenticate(user)

    response = api_client.get(COUNT_URL)

    assert response.json() == {"unread": 1}


def test_a_user_can_mark_one_notification_as_read(api_client, user):
    notification = notify(user, "post_published", "One.")
    api_client.force_authenticate(user)

    response = api_client.post(f"{LIST_URL}{notification.id}/read/")

    assert response.status_code == 200
    assert response.json()["read_at"] is not None


def test_nobody_can_mark_someone_elses_notification(api_client, user, other_user):
    notification = notify(other_user, "post_published", "Private.")
    api_client.force_authenticate(user)

    response = api_client.post(f"{LIST_URL}{notification.id}/read/")

    assert response.status_code == 404
    notification.refresh_from_db()
    assert notification.read_at is None


def test_read_all_marks_only_the_users_own_notifications(api_client, user, other_user):
    notify(user, "post_published", "One.")
    notify(user, "post_published", "Two.")
    notify(other_user, "post_published", "Not yours.")
    api_client.force_authenticate(user)

    response = api_client.post(READ_ALL_URL)

    assert response.json() == {"marked_read": 2}
    assert Notification.objects.filter(read_at=None).count() == 1


def test_me_summary_shows_the_unread_count(api_client, user):
    notify(user, "post_published", "One.")
    api_client.force_authenticate(user)

    response = api_client.get("/api/v1/me/summary/")

    assert response.json()["unread_notifications"] == 1
