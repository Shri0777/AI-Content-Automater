"""Linking X accounts, posting to them, refreshing and revoking tokens."""

import base64
from datetime import timedelta

from django.utils import timezone

from core.crypto import decrypt_text
from social.models import SocialAccount
from social.oauth import make_code_challenge
from social.platforms import get_publisher
from social.publishers import PostContent
from social.tests.linking import finish_link, link_with_oauth, start_link
from social.tokens import REFRESH_BEFORE_POSTING, refresh_account
from tests.social_stubs import (
    X_REVOKE_PATH,
    X_TOKEN_PATH,
    X_TWEETS_PATH,
    X_UPLOAD_PATH,
    add_x_routes,
)


def link_x_account(client, platforms):
    """Link an X account through the whole OAuth flow and return it."""
    add_x_routes(platforms)
    response = link_with_oauth(client, "x")
    assert response.status_code == 302
    assert "result=linked" in response["Location"]
    return SocialAccount.objects.get(platform="x")


def test_the_approval_page_asks_for_posting_scopes_with_pkce(client, platforms):
    approval = start_link(client, "x")

    assert approval["client_id"] == "x-app"
    assert approval["response_type"] == "code"
    assert approval["code_challenge_method"] == "S256"
    assert "media.write" in approval["scope"]
    assert "offline.access" in approval["scope"]
    assert approval["redirect_uri"].endswith("/api/v1/social/link/x/callback/")


def test_linking_saves_the_account_with_encrypted_tokens(client, platforms):
    account = link_x_account(client, platforms)

    assert account.display_name == "@ada_dev"
    assert account.external_id == "2244994945"
    assert account.status == "active"
    assert "access-1" not in account.encrypted_token
    assert decrypt_text(account.encrypted_token) == "access-1"
    assert decrypt_text(account.encrypted_refresh_token) == "refresh-1"
    assert account.token_expires_at > timezone.now() + timedelta(minutes=110)


def test_the_code_swap_sends_the_pkce_secret_and_the_app_password(client, platforms):
    add_x_routes(platforms)
    approval = start_link(client, "x")

    finish_link("x", {"code": "code-123", "state": approval["state"]})

    token_request = platforms.requests_to(X_TOKEN_PATH)[0]
    verifier = token_request["form"]["code_verifier"]
    assert make_code_challenge(verifier) == approval["code_challenge"]
    expected = base64.b64encode(b"x-app:x-app-secret").decode()
    assert token_request["headers"]["Authorization"] == f"Basic {expected}"


def test_publishing_uploads_the_poster_then_posts_with_it(client, platforms):
    account = link_x_account(client, platforms)
    content = PostContent("Hello from the stub", b"PNG-BYTES", "")

    post_id = get_publisher("x").publish(account, content)

    assert post_id == "1445880548472328192"
    upload = platforms.requests_to(X_UPLOAD_PATH)[0]
    assert b"PNG-BYTES" in upload["raw_body"]
    assert upload["headers"]["Authorization"] == "Bearer access-1"
    tweet = platforms.requests_to(X_TWEETS_PATH)[0]["body"]
    assert tweet == {
        "text": "Hello from the stub",
        "media": {"media_ids": ["1880028106020515840"]},
    }


def test_a_token_about_to_expire_is_swapped_for_new_ones(client, platforms):
    account = link_x_account(client, platforms)
    account.token_expires_at = timezone.now() + timedelta(minutes=5)
    account.save()

    account = refresh_account(account.id, REFRESH_BEFORE_POSTING)

    assert decrypt_text(account.encrypted_token) == "access-2"
    assert decrypt_text(account.encrypted_refresh_token) == "refresh-2"
    refresh_request = platforms.requests_to(X_TOKEN_PATH)[1]["form"]
    assert refresh_request == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-1",
    }


def test_a_fresh_token_is_not_refreshed(client, platforms):
    account = link_x_account(client, platforms)

    refresh_account(account.id, REFRESH_BEFORE_POSTING)

    assert len(platforms.requests_to(X_TOKEN_PATH)) == 1


def test_unlinking_revokes_the_grant_at_x(client, platforms):
    account = link_x_account(client, platforms)

    response = client.delete(f"/api/v1/social/accounts/{account.id}/")

    assert response.status_code == 204
    assert platforms.requests_to(X_REVOKE_PATH)[0]["form"] == {"token": "refresh-1"}
    assert not SocialAccount.objects.filter(id=account.id).exists()


def test_unlinking_still_works_when_x_cannot_be_reached(client, platforms):
    account = link_x_account(client, platforms)
    platforms.set_route("POST", X_REVOKE_PATH, {"status": 503, "json": {}})

    response = client.delete(f"/api/v1/social/accounts/{account.id}/")

    assert response.status_code == 204
    assert not SocialAccount.objects.filter(id=account.id).exists()
