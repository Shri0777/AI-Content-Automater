"""Tests for notify(), the one function every feature uses to tell a user something."""

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from notifications.models import Notification
from notifications.services import delete_old_notifications, mark_read, notify


@pytest.fixture
def user(db):
    """A saved user."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


def test_notify_creates_an_unread_notification_with_a_title(user):
    notification = notify(user, "post_published", "Your post is live on LinkedIn.")

    assert notification.title == "Post published"
    assert notification.message == "Your post is live on LinkedIn."
    assert notification.read_at is None


def test_notify_can_point_to_a_related_item(user):
    notification = notify(user, "quota_reached", "Limit reached.", related=user)

    assert notification.related_type == "user"
    assert notification.related_id == user.id


def test_an_unknown_kind_is_a_programming_error(user):
    with pytest.raises(ValueError):
        notify(user, "pizza_delivered", "Hot and fresh.")


def test_repeats_with_the_same_dedupe_key_are_collapsed(user):
    notify(user, "credential_invalid", "Key failed.", dedupe_key="credential-1")
    notify(user, "credential_invalid", "Key failed.", dedupe_key="credential-1")

    assert Notification.objects.count() == 1


def test_a_repeat_after_the_first_was_read_creates_a_new_notification(user):
    first = notify(user, "credential_invalid", "Key failed.", dedupe_key="cred-1")
    mark_read(user, first.id)

    notify(user, "credential_invalid", "Key failed again.", dedupe_key="cred-1")

    assert Notification.objects.count() == 2


def test_notifications_older_than_60_days_are_deleted(user):
    with freeze_time("2026-01-01"):
        notify(user, "post_published", "Old news.")
    with freeze_time("2026-03-01"):
        notify(user, "post_published", "Recent news.")

    with freeze_time("2026-03-10"):
        deleted_count = delete_old_notifications()

    assert deleted_count == 1
    assert Notification.objects.get().message == "Recent news."
