"""Tests for saving the API keys of a user's AI and news providers."""

import pytest
from django.contrib.auth import get_user_model

from credentials.models import ProviderCredential
from credentials.services import get_credential, read_api_key
from tests.provider_stubs import add_provider_routes

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


def save_real(client, adapter, changes=None):
    """Save a real-provider credential through the API and return the response.

    changes is a dict of fields that replace the usual values.
    """
    data = {
        "kind": "text",
        "adapter": adapter,
        "model_name": "claude-opus-5-5",
        "api_key": "sk-secret-1234",
    }
    data.update(changes or {})
    return client.post(URL, data, format="json")


def test_a_real_provider_needs_a_model_name(client):
    response = save_real(client, "anthropic", {"model_name": ""})

    assert response.status_code == 400
    assert "model_name" in response.json()["errors"]


def test_providers_that_need_a_key_refuse_to_save_without_one(client):
    response = save_real(client, "anthropic", {"api_key": ""})

    assert response.status_code == 400
    assert "api_key" in response.json()["errors"]


def test_a_local_model_server_may_be_saved_without_a_key(client, settings):
    settings.ALLOW_PRIVATE_PROVIDER_URLS = True

    response = save_real(
        client,
        "openai_compatible",
        {
            "model_name": "llama3.2",
            "base_url": "http://localhost:11434/v1",
            "api_key": "",
        },
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "model_name", ["../../admin", "model name", "-flag", "name?x=1"]
)
def test_model_names_cannot_change_the_providers_address(client, model_name):
    response = save_real(client, "anthropic", {"model_name": model_name})

    assert response.status_code == 400


@pytest.mark.parametrize(
    "base_url", ["http://api.example.com", "file:///etc/passwd", "https://u:p@x.com"]
)
def test_unsafe_custom_addresses_are_refused(client, base_url):
    response = save_real(client, "anthropic", {"base_url": base_url})

    assert response.status_code == 400
    assert "base_url" in response.json()["errors"]


def test_a_new_credential_starts_unchecked(client):
    body = save_real(client, "anthropic").json()

    assert body["status"] == "unverified"
    assert body["last_checked_at"] is None


def check(client, credential_id):
    """Run "test connection" on a credential and return the response."""
    return client.post(f"{URL}{credential_id}/test/")


def test_a_working_key_is_marked_verified(client, stub_server):
    add_provider_routes(stub_server)
    credential_id = save_real(
        client, "anthropic", {"base_url": stub_server.base_url}
    ).json()["id"]

    body = check(client, credential_id).json()

    assert body["status"] == "verified"
    assert body["last_checked_at"] is not None
    assert body["last_error"] == ""


def test_a_refused_key_is_marked_invalid(client, stub_server):
    stub_server.set_route("GET", "/v1/models/claude-opus-5-5", {"status": 401})
    credential_id = save_real(
        client, "anthropic", {"base_url": stub_server.base_url}
    ).json()["id"]

    body = check(client, credential_id).json()

    assert body["status"] == "invalid"
    assert "API key" in body["last_error"]


def test_a_provider_outage_leaves_the_key_unchecked_with_a_reason(client, stub_server):
    stub_server.set_route("GET", "/v1/models/claude-opus-5-5", {"status": 503})
    credential_id = save_real(
        client, "anthropic", {"base_url": stub_server.base_url}
    ).json()["id"]

    body = check(client, credential_id).json()

    assert body["status"] == "unverified"
    assert "busy" in body["last_error"]


def test_saving_a_new_key_clears_the_old_check(client, stub_server):
    add_provider_routes(stub_server)
    credential_id = save_real(
        client, "anthropic", {"base_url": stub_server.base_url}
    ).json()["id"]
    check(client, credential_id)

    body = save_real(client, "anthropic", {"base_url": stub_server.base_url}).json()

    assert body["status"] == "unverified"


def test_nobody_can_check_another_users_key(client):
    other = make_user("grace@example.com")
    theirs = ProviderCredential.objects.create(user=other, kind="text", adapter="demo")

    assert check(client, theirs.id).status_code == 404


def test_checking_keys_is_rate_limited(client):
    credential_id = save(client, "text").json()["id"]

    statuses = []
    for _ in range(11):
        statuses.append(check(client, credential_id).status_code)

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429
