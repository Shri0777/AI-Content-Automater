"""Tests for linking social accounts (only the demo network so far)."""

import pytest
from django.contrib.auth import get_user_model

from social.models import SocialAccount

ACCOUNTS_URL = "/api/v1/social/accounts/"
LINK_DEMO_URL = "/api/v1/social/link/demo/"


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
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client


def test_social_accounts_need_a_login(api_client, db):
    assert api_client.get(ACCOUNTS_URL).status_code == 401


def test_linking_the_demo_network_creates_an_active_account(client):
    response = client.post(LINK_DEMO_URL)

    assert response.status_code == 201
    body = response.json()
    assert body["platform"] == "demo"
    assert body["status"] == "active"
    assert "token" not in str(body).lower()


def test_linked_accounts_are_listed(client):
    client.post(LINK_DEMO_URL)
    client.post(LINK_DEMO_URL)

    accounts = client.get(ACCOUNTS_URL).json()

    assert len(accounts) == 2
    assert accounts[0]["display_name"] != accounts[1]["display_name"]


def test_the_demo_network_is_refused_outside_demo_mode(client, settings):
    settings.DEMO_MODE = False

    response = client.post(LINK_DEMO_URL)

    assert response.status_code == 400
    assert response.json()["code"] == "demo_mode_off"


def test_a_user_cannot_link_more_accounts_than_their_limit(client):
    for _ in range(5):
        assert client.post(LINK_DEMO_URL).status_code == 201

    response = client.post(LINK_DEMO_URL)

    assert response.status_code == 403
    assert response.json()["code"] == "quota_exceeded"
    assert SocialAccount.objects.count() == 5


def test_users_only_see_and_unlink_their_own_accounts(client):
    other = make_user("grace@example.com")
    theirs = SocialAccount.objects.create(
        user=other, platform="demo", display_name="Grace", external_id="g-1"
    )

    assert client.get(ACCOUNTS_URL).json() == []
    assert client.delete(f"{ACCOUNTS_URL}{theirs.id}/").status_code == 404
    assert SocialAccount.objects.filter(id=theirs.id).exists()


def test_a_user_can_unlink_their_account(client):
    account_id = client.post(LINK_DEMO_URL).json()["id"]

    response = client.delete(f"{ACCOUNTS_URL}{account_id}/")

    assert response.status_code == 204
    assert not SocialAccount.objects.exists()
