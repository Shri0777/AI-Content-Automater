"""Tests for /api/v1/me/, where users see and change their own details."""

import pytest
from django.contrib.auth import get_user_model

ME_URL = "/api/v1/me/"


@pytest.fixture
def user(db):
    """A saved user."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


def test_me_needs_a_login(api_client, db):
    response = api_client.get(ME_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_me_shows_the_logged_in_users_details(api_client, user):
    api_client.force_authenticate(user)

    response = api_client.get(ME_URL)

    assert response.json() == {
        "id": str(user.id),
        "email": "ada@example.com",
        "timezone": "UTC",
        "tier": "free",
        "date_joined": response.json()["date_joined"],
    }


def test_a_user_can_change_their_timezone(api_client, user):
    api_client.force_authenticate(user)

    response = api_client.patch(ME_URL, {"timezone": "Asia/Kolkata"}, format="json")

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.timezone == "Asia/Kolkata"


def test_an_unknown_timezone_is_refused(api_client, user):
    api_client.force_authenticate(user)

    response = api_client.patch(ME_URL, {"timezone": "Mars/Base"}, format="json")

    assert response.status_code == 400
    assert "timezone" in response.json()["errors"]


def test_users_cannot_change_their_own_tier(api_client, user):
    api_client.force_authenticate(user)

    api_client.patch(ME_URL, {"tier": "unlimited"}, format="json")

    user.refresh_from_db()
    assert user.tier == "free"
