"""Linking Facebook Pages and posting photos to them."""

from core.crypto import decrypt_text
from social.models import SocialAccount
from social.platforms import get_publisher
from social.publishers import PostContent
from social.tests.linking import link_with_oauth, start_link
from tests.social_stubs import (
    FACEBOOK_PHOTOS_PATH,
    FACEBOOK_TOKEN_PATH,
    add_facebook_routes,
    facebook_page,
)


def test_the_approval_page_asks_for_page_posting(client, platforms):
    approval = start_link(client, "facebook")

    assert "pages_manage_posts" in approval["scope"]
    assert approval["client_id"] == "fb-app"


def test_only_pages_the_user_may_post_to_are_linked(client, platforms):
    pages = [
        facebook_page("page-1", ["ANALYZE", "CREATE_CONTENT", "MANAGE"]),
        facebook_page("page-2", ["ANALYZE"]),
    ]
    add_facebook_routes(platforms, pages)

    response = link_with_oauth(client, "facebook")

    assert "result=linked" in response["Location"]
    account = SocialAccount.objects.get()
    assert account.external_id == "page-1"
    assert decrypt_text(account.encrypted_token) == "page-token-page-1"
    assert account.token_expires_at is None


def test_the_short_token_is_swapped_for_a_long_lived_one(client, platforms):
    add_facebook_routes(platforms, [facebook_page("page-1", ["CREATE_CONTENT"])])

    link_with_oauth(client, "facebook")

    first, second = platforms.requests_to(FACEBOOK_TOKEN_PATH)
    assert first["query"]["code"] == "code-123"
    assert second["query"]["grant_type"] == "fb_exchange_token"
    assert second["query"]["fb_exchange_token"] == "access-1"


def test_no_page_to_post_to_sends_the_user_back_with_an_error(client, platforms):
    add_facebook_routes(platforms, [facebook_page("page-2", ["ANALYZE"])])

    response = link_with_oauth(client, "facebook")

    assert "result=error" in response["Location"]
    assert "reason=platform_error" in response["Location"]
    assert not SocialAccount.objects.exists()


def test_publishing_uploads_the_photo_with_its_caption(client, platforms):
    add_facebook_routes(platforms, [facebook_page("page-1", ["CREATE_CONTENT"])])
    link_with_oauth(client, "facebook")
    account = SocialAccount.objects.get()

    post_id = get_publisher("facebook").publish(
        account, PostContent("Our caption", b"PNG-BYTES", "")
    )

    assert post_id == "page-1_9876543210"
    upload = platforms.requests_to(FACEBOOK_PHOTOS_PATH)[0]["raw_body"]
    assert b"PNG-BYTES" in upload
    assert b"Our caption" in upload
    assert b"page-token-page-1" in upload
