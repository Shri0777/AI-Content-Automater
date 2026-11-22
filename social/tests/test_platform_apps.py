"""Users bring their own developer app for X, LinkedIn and Facebook.

Linking directly to these platforms needs an app registered with each one
(an id and a secret). Each user saves their own in the app; the server's
.env app, if any, is only a fallback.
"""

import base64
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.crypto import decrypt_text
from social.models import PlatformApp, SocialAccount
from social.tests.linking import finish_link, link_with_oauth, start_link
from social.tokens import REFRESH_BEFORE_POSTING, refresh_account
from tests.social_stubs import (
    FACEBOOK_TOKEN_PATH,
    LINKEDIN_TOKEN_PATH,
    X_TOKEN_PATH,
    add_facebook_routes,
    add_linkedin_routes,
    add_x_routes,
    facebook_page,
)

APPS_URL = "/api/v1/social/apps/"
PLATFORMS_URL = "/api/v1/social/platforms/"


@pytest.fixture
def no_server_apps(platforms, settings):
    """The stub platforms, with no app set up in the server's .env."""
    settings.SOCIAL_APPS = {
        name: {"client_id": "", "client_secret": ""}
        for name in ["x", "linkedin", "facebook"]
    }
    return platforms


def save_app(client, platform, client_id="my-app", client_secret="my-secret"):
    """Save the user's own developer app for a platform."""
    body = {"client_id": client_id, "client_secret": client_secret}
    return client.put(f"{APPS_URL}{platform}/", body, format="json")


def platform_entry(client, platform):
    """Return one platform's entry from the platform list."""
    for entry in client.get(PLATFORMS_URL).json():
        if entry["platform"] == platform:
            return entry
    raise AssertionError(f"{platform} is not in the platform list")


def basic_auth(client_id, client_secret):
    """Return the Basic Authorization header X expects from an app."""
    pair = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(pair).decode()


def test_without_an_app_direct_platforms_cannot_be_linked(client, no_server_apps):
    response = client.post("/api/v1/social/link/x/start/")

    assert platform_entry(client, "x")["ready"] is False
    assert response.status_code == 400
    assert response.json()["code"] == "platform_not_ready"


def test_saving_your_own_app_makes_the_platform_ready_for_you_only(
    client, other_user, no_server_apps
):
    response = save_app(client, "x")
    other_client = APIClient()
    other_client.force_authenticate(other_user)

    assert response.status_code == 200
    assert platform_entry(client, "x")["ready"] is True
    assert platform_entry(client, "x")["app_saved"] is True
    assert platform_entry(other_client, "x")["ready"] is False


def test_the_secret_is_stored_encrypted_and_never_sent_back(client, no_server_apps):
    response = save_app(client, "x")
    listed = client.get(APPS_URL).json()

    app = PlatformApp.objects.get(platform="x")
    assert app.encrypted_client_secret != "my-secret"
    assert decrypt_text(app.encrypted_client_secret) == "my-secret"
    assert "my-secret" not in str(response.json())
    assert [(item["platform"], item["client_id"]) for item in listed] == [
        ("x", "my-app")
    ]
    assert "my-secret" not in str(listed)


def test_saving_again_replaces_the_app(client, no_server_apps):
    save_app(client, "x")
    save_app(client, "x", client_id="new-app", client_secret="new-secret")

    app = PlatformApp.objects.get(platform="x")
    assert app.client_id == "new-app"
    assert decrypt_text(app.encrypted_client_secret) == "new-secret"


def test_linking_x_uses_your_app_id_and_secret(client, no_server_apps):
    add_x_routes(no_server_apps)
    save_app(client, "x")

    approval = start_link(client, "x")
    finish_link("x", {"code": "code-123", "state": approval["state"]})

    assert approval["client_id"] == "my-app"
    token_request = no_server_apps.requests_to(X_TOKEN_PATH)[0]
    expected = basic_auth("my-app", "my-secret")
    assert token_request["headers"]["Authorization"] == expected


def test_refreshing_tokens_uses_your_app(client, no_server_apps):
    add_x_routes(no_server_apps)
    save_app(client, "x")
    link_with_oauth(client, "x")
    account = SocialAccount.objects.get(platform="x")
    account.token_expires_at = timezone.now() + timedelta(minutes=5)
    account.save()

    refresh_account(account.id, REFRESH_BEFORE_POSTING)

    refresh_request = no_server_apps.requests_to(X_TOKEN_PATH)[1]
    expected = basic_auth("my-app", "my-secret")
    assert refresh_request["headers"]["Authorization"] == expected


def test_linking_linkedin_uses_your_app(client, no_server_apps):
    add_linkedin_routes(no_server_apps)
    save_app(client, "linkedin", "li-mine", "li-mine-secret")

    response = link_with_oauth(client, "linkedin")

    assert "result=linked" in response["Location"]
    form = no_server_apps.requests_to(LINKEDIN_TOKEN_PATH)[0]["form"]
    assert (form["client_id"], form["client_secret"]) == ("li-mine", "li-mine-secret")


def test_linking_facebook_uses_your_app(client, no_server_apps):
    add_facebook_routes(no_server_apps, [facebook_page("page-1", ["CREATE_CONTENT"])])
    save_app(client, "facebook", "fb-mine", "fb-mine-secret")

    response = link_with_oauth(client, "facebook")

    assert "result=linked" in response["Location"]
    query = no_server_apps.requests_to(FACEBOOK_TOKEN_PATH)[0]["query"]
    assert (query["client_id"], query["client_secret"]) == ("fb-mine", "fb-mine-secret")


def test_your_app_is_used_instead_of_the_servers(client, platforms):
    save_app(client, "x")

    approval = start_link(client, "x")

    assert approval["client_id"] == "my-app"


def test_removing_your_app_makes_the_platform_unavailable_again(client, no_server_apps):
    save_app(client, "x")

    response = client.delete(f"{APPS_URL}x/")

    assert response.status_code == 204
    assert platform_entry(client, "x")["ready"] is False
    assert PlatformApp.objects.count() == 0


def test_you_cannot_see_or_remove_another_users_app(client, other_user, no_server_apps):
    other_client = APIClient()
    other_client.force_authenticate(other_user)
    save_app(other_client, "x")

    assert client.get(APPS_URL).json() == []
    assert client.delete(f"{APPS_URL}x/").status_code == 404
    assert PlatformApp.objects.filter(user=other_user).count() == 1


def test_only_platforms_linked_with_an_app_take_one(client, no_server_apps):
    response = save_app(client, "buffer")

    assert response.status_code == 404
    assert response.json()["code"] == "platform_app_not_found"


def test_the_id_and_secret_are_both_required(client, no_server_apps):
    response = save_app(client, "x", client_id=" ", client_secret="")

    assert response.status_code == 400
    assert set(response.json()["errors"]) == {"client_id", "client_secret"}


def test_the_platform_list_says_where_the_platform_must_send_users_back(
    client, no_server_apps
):
    entry = platform_entry(client, "x")

    expected = "http://127.0.0.1:8000/api/v1/social/link/x/callback/"
    assert entry["callback_url"] == expected
    assert entry["app_saved"] is False
    assert platform_entry(client, "buffer")["callback_url"] is None
