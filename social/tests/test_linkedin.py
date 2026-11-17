"""Linking LinkedIn members and posting to them; tokens cannot be refreshed."""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.errors import ProviderError
from notifications.models import Notification
from social.models import SocialAccount
from social.platforms import get_publisher
from social.publishers import PostContent
from social.tests.linking import link_with_oauth, start_link
from social.tokens import (
    REFRESH_BEFORE_POSTING,
    refresh_account,
    refresh_expiring_accounts,
)
from tests.social_stubs import (
    LINKEDIN_IMAGES_PATH,
    LINKEDIN_POSTS_PATH,
    LINKEDIN_TOKEN_PATH,
    LINKEDIN_UPLOAD_PATH,
    add_linkedin_routes,
)


def link_linkedin_account(client, platforms):
    """Link a LinkedIn member through the whole OAuth flow and return it."""
    add_linkedin_routes(platforms)
    response = link_with_oauth(client, "linkedin")
    assert "result=linked" in response["Location"]
    return SocialAccount.objects.get(platform="linkedin")


def test_the_approval_page_asks_to_post_as_the_member(client, platforms):
    approval = start_link(client, "linkedin")

    assert approval["scope"] == "openid profile w_member_social"
    assert approval["client_id"] == "li-app"


def test_linking_uses_the_members_id_and_name(client, platforms):
    account = link_linkedin_account(client, platforms)

    assert account.external_id == "782bbtaQ"
    assert account.display_name == "Ada Lovelace"
    assert account.encrypted_refresh_token == ""
    token_form = platforms.requests_to(LINKEDIN_TOKEN_PATH)[0]["form"]
    assert token_form["client_secret"] == "li-app-secret"
    assert token_form["grant_type"] == "authorization_code"


def test_publishing_uploads_the_image_then_creates_the_post(client, platforms):
    account = link_linkedin_account(client, platforms)
    content = PostContent("A caption", b"PNG-BYTES", "")

    post_id = get_publisher("linkedin").publish(account, content)

    assert post_id == "urn:li:share:6844785523593134080"
    start = platforms.requests_to(LINKEDIN_IMAGES_PATH)[0]
    assert start["query"] == {"action": "initializeUpload"}
    assert start["body"]["initializeUploadRequest"]["owner"] == "urn:li:person:782bbtaQ"
    assert start["headers"]["LinkedIn-Version"] == "202610"
    assert start["headers"]["X-Restli-Protocol-Version"] == "2.0.0"
    assert platforms.requests_to(LINKEDIN_UPLOAD_PATH)[0]["raw_body"] == b"PNG-BYTES"
    post = platforms.requests_to(LINKEDIN_POSTS_PATH)[0]["body"]
    assert post["author"] == "urn:li:person:782bbtaQ"
    assert post["commentary"] == "A caption"
    assert post["content"] == {"media": {"id": "urn:li:image:C4E10AQFoyyAjHPMQuQ"}}


def test_a_post_without_an_id_header_is_an_error(client, platforms):
    account = link_linkedin_account(client, platforms)
    platforms.set_route("POST", LINKEDIN_POSTS_PATH, {"status": 201, "body": b""})

    with pytest.raises(ProviderError, match="did not say which post"):
        get_publisher("linkedin").publish(account, PostContent("x", b"P", ""))


def test_an_expired_token_that_cannot_be_refreshed_needs_a_new_link(client, platforms):
    account = link_linkedin_account(client, platforms)
    account.token_expires_at = timezone.now() - timedelta(minutes=1)
    account.save()

    account = refresh_account(account.id, REFRESH_BEFORE_POSTING)

    assert account.status == "needs_reauth"
    assert Notification.objects.filter(kind="account_needs_reauth").count() == 1


def test_owners_are_warned_once_a_week_before_the_link_ends(client, platforms):
    account = link_linkedin_account(client, platforms)
    account.token_expires_at = timezone.now() + timedelta(days=3)
    account.save()

    refresh_expiring_accounts()
    refresh_expiring_accounts()

    warnings = Notification.objects.filter(kind="account_needs_reauth")
    assert warnings.count() == 1
    assert "Link it again" in warnings[0].message
    account.refresh_from_db()
    assert account.status == "active"
