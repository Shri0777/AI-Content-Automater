"""Tests for logging in, refreshing the login and logging out.

The access token is returned in the response body. The refresh token is
kept in an httpOnly cookie that browser scripts cannot read (ADR-009).
"""

import pytest
from django.contrib.auth import get_user_model

from accounts import refresh_replay

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
PASSWORD = "correct-horse-battery-staple"
HEADER = {"HTTP_X_REQUESTED_BY": "test-suite"}


@pytest.fixture
def user(db):
    """A saved user who can log in."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password=PASSWORD
    )


def log_in(api_client):
    """Log in as the test user and return the response."""
    data = {"email": "ada@example.com", "password": PASSWORD}
    return api_client.post(LOGIN_URL, data, format="json")


def test_login_returns_an_access_token(api_client, user):
    response = log_in(api_client)

    assert response.status_code == 200
    assert response.json()["access"] != ""
    assert response.json()["user"]["email"] == "ada@example.com"


def test_login_puts_the_refresh_token_in_a_protected_cookie(api_client, user):
    response = log_in(api_client)

    cookie = response.cookies["refresh_token"]
    assert cookie.value != ""
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["secure"] is True
    assert "refresh" not in response.json()


def test_wrong_password_is_refused(api_client, user):
    data = {"email": "ada@example.com", "password": "wrong-password"}

    response = api_client.post(LOGIN_URL, data, format="json")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_the_access_token_opens_protected_endpoints(api_client, user):
    access = log_in(api_client).json()["access"]

    response = api_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {access}")

    assert response.status_code == 200


def test_refresh_gives_a_new_access_token_and_a_new_cookie(api_client, user):
    first_cookie = log_in(api_client).cookies["refresh_token"].value

    response = api_client.post(REFRESH_URL, **HEADER)

    assert response.status_code == 200
    assert response.json()["access"] != ""
    assert response.cookies["refresh_token"].value != first_cookie


def test_refresh_without_the_required_header_is_refused(api_client, user):
    log_in(api_client)

    response = api_client.post(REFRESH_URL)

    assert response.status_code == 403
    assert response.json()["code"] == "missing_required_header"


def test_refresh_without_a_cookie_is_refused(api_client, user):
    response = api_client.post(REFRESH_URL, **HEADER)

    assert response.status_code == 401
    assert response.json()["code"] == "not_logged_in"


def test_an_old_refresh_token_cannot_be_reused_after_the_replay_window(
    api_client, user, monkeypatch
):
    monkeypatch.setattr(refresh_replay, "REFRESH_REPLAY_SECONDS", 0)
    old_cookie = log_in(api_client).cookies["refresh_token"].value
    api_client.post(REFRESH_URL, **HEADER)
    api_client.cookies["refresh_token"] = old_cookie

    response = api_client.post(REFRESH_URL, **HEADER)

    assert response.status_code == 401


def test_a_just_swapped_refresh_token_gets_the_same_answer_again(api_client, user):
    # Two tabs refreshing together, or a reload that dropped the reply with
    # the new cookie, must not log the user out.
    old_cookie = log_in(api_client).cookies["refresh_token"].value
    first = api_client.post(REFRESH_URL, **HEADER)
    # Read it now: setting the client's cookie below changes this one too.
    new_cookie = first.cookies["refresh_token"].value
    api_client.cookies["refresh_token"] = old_cookie

    again = api_client.post(REFRESH_URL, **HEADER)

    assert again.status_code == 200
    assert again.json()["access"] == first.json()["access"]
    assert again.cookies["refresh_token"].value == new_cookie


def test_a_just_swapped_refresh_token_is_refused_after_logout(api_client, user):
    old_cookie = log_in(api_client).cookies["refresh_token"].value
    api_client.post(REFRESH_URL, **HEADER)
    api_client.post(LOGOUT_URL, **HEADER)
    api_client.cookies["refresh_token"] = old_cookie

    response = api_client.post(REFRESH_URL, **HEADER)

    assert response.status_code == 401


def test_logout_clears_the_cookie_and_cancels_the_refresh_token(api_client, user):
    old_cookie = log_in(api_client).cookies["refresh_token"].value

    response = api_client.post(LOGOUT_URL, **HEADER)

    assert response.status_code == 204
    assert response.cookies["refresh_token"]["max-age"] == 0
    api_client.cookies["refresh_token"] = old_cookie
    assert api_client.post(REFRESH_URL, **HEADER).status_code == 401


def test_too_many_login_attempts_are_slowed_down(api_client, user):
    data = {"email": "ada@example.com", "password": "wrong-password"}
    for _ in range(10):
        api_client.post(LOGIN_URL, data, format="json")

    response = api_client.post(LOGIN_URL, data, format="json")

    assert response.status_code == 429
    assert response.json()["code"] == "throttled"


def test_refreshing_has_its_own_looser_limit_than_logging_in(api_client, user):
    # Every page load refreshes the login. Sharing the strict 10-a-minute
    # login limit would log out anyone who opens a few tabs.
    log_in(api_client)
    for _ in range(15):
        response = api_client.post(REFRESH_URL, **HEADER)
        assert response.status_code == 200
