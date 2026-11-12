"""Tests for saving the API keys of a user's AI and news providers."""

import pytest
from django.contrib.auth import get_user_model

from credentials.models import ProviderCredential
from credentials.services import get_credential, read_api_key

URL = "/api/v1/credentials/"


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


def save(client, kind, adapter="demo", api_key="sk-secret-1234"):
    """Save a credential through the API and return the response."""
    data = {"kind": kind, "adapter": adapter, "api_key": api_key}
    return client.post(URL, data, format="json")


def test_credentials_need_a_login(api_client, db):
    assert api_client.get(URL).status_code == 401


def test_saving_a_key_never_shows_it_again(client):
    response = save(client, "text")

    assert response.status_code == 201
    assert "api_key" not in response.json()
    assert response.json()["key_hint"] == "1234"


def test_keys_are_stored_encrypted(client, user):
    save(client, "text")

    saved = ProviderCredential.objects.get()
    assert "sk-secret-1234" not in saved.encrypted_key
    assert read_api_key(get_credential(user, "text")) == "sk-secret-1234"


def test_saving_the_same_kind_again_replaces_the_old_key(client):
    save(client, "image", api_key="first-key-aaaa")
    save(client, "image", api_key="second-key-bbbb")

    assert ProviderCredential.objects.count() == 1
    assert ProviderCredential.objects.get().key_hint == "bbbb"


def test_text_image_and_news_keys_are_kept_separately(client):
    save(client, "text")
    save(client, "image")
    save(client, "news")

    kinds = [item["kind"] for item in client.get(URL).json()]
    assert sorted(kinds) == ["image", "news", "text"]


def test_an_unknown_provider_is_refused(client):
    response = save(client, "text", adapter="mystery-ai")

    assert response.status_code == 400
    assert "adapter" in response.json()["errors"]


def test_demo_providers_are_refused_outside_demo_mode(client, settings):
    settings.DEMO_MODE = False

    response = save(client, "text")

    assert response.status_code == 400
    assert "adapter" in response.json()["errors"]


def test_users_only_see_and_delete_their_own_keys(client, db):
    other = make_user("grace@example.com")
    theirs = ProviderCredential.objects.create(user=other, kind="text", adapter="demo")

    assert client.get(URL).json() == []
    assert client.delete(f"{URL}{theirs.id}/").status_code == 404
    assert ProviderCredential.objects.filter(id=theirs.id).exists()


def test_a_user_can_delete_their_key(client):
    credential_id = save(client, "text").json()["id"]

    response = client.delete(f"{URL}{credential_id}/")

    assert response.status_code == 204
    assert not ProviderCredential.objects.exists()
