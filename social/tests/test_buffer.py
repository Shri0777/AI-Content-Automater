"""Linking Buffer channels with an API key, and posting through Buffer."""

import pytest

from core.crypto import decrypt_text
from core.errors import ProviderError
from social.models import SocialAccount
from social.platforms import caption_limit_for, get_publisher
from social.publishers import PostContent
from tests.social_stubs import BUFFER_PATH, add_buffer_routes

LINK_BUFFER_URL = "/api/v1/social/link/buffer/"
PUBLIC_POSTER = "https://automator.example.com/api/v1/public/posters/abc.png"


def test_every_channel_in_every_organisation_is_linked(client, platforms):
    add_buffer_routes(platforms)

    response = client.post(LINK_BUFFER_URL, {"api_key": "buffer-key-1"}, format="json")

    assert response.status_code == 201
    names = [account["display_name"] for account in response.json()]
    assert names == [
        "Ada org-1 (linkedin via Buffer)",
        "Ada org-2 (linkedin via Buffer)",
    ]
    assert "buffer-key-1" not in str(response.json())
    account = SocialAccount.objects.first()
    assert account.network == "linkedin"
    assert decrypt_text(account.encrypted_token) == "buffer-key-1"
    request = platforms.requests_to(BUFFER_PATH)[0]
    assert request["headers"]["Authorization"] == "Bearer buffer-key-1"


def test_only_the_chosen_channels_are_linked(client, platforms):
    add_buffer_routes(platforms)

    client.post(
        LINK_BUFFER_URL,
        {"api_key": "buffer-key-1", "channel_ids": ["channel-org-2"]},
        format="json",
    )

    assert list(SocialAccount.objects.values_list("external_id", flat=True)) == [
        "channel-org-2"
    ]


def test_a_refused_key_is_a_clear_error(client, platforms):
    platforms.set_route("POST", BUFFER_PATH, {"status": 401, "json": {}})

    response = client.post(LINK_BUFFER_URL, {"api_key": "wrong-key"}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "platform_refused"
    assert not SocialAccount.objects.exists()


def test_a_buffer_channel_uses_its_networks_caption_limit(client, platforms):
    add_buffer_routes(platforms)
    client.post(LINK_BUFFER_URL, {"api_key": "buffer-key-1"}, format="json")

    assert caption_limit_for(SocialAccount.objects.first()) == 3000


def test_publishing_sends_the_public_poster_link(client, platforms):
    add_buffer_routes(platforms)
    client.post(LINK_BUFFER_URL, {"api_key": "buffer-key-1"}, format="json")
    account = SocialAccount.objects.first()

    post_id = get_publisher("buffer").publish(
        account, PostContent("Caption", b"", PUBLIC_POSTER)
    )

    assert post_id == "buffer-post-1"
    post_input = platforms.requests_to(BUFFER_PATH)[-1]["body"]["variables"]["input"]
    assert post_input["channelId"] == "channel-org-1"
    assert post_input["assets"] == [{"image": {"url": PUBLIC_POSTER}}]
    assert post_input["mode"] == "customScheduled"
    assert post_input["dueAt"].endswith(".000Z")


def test_an_error_from_buffer_fails_the_post(client, platforms):
    add_buffer_routes(platforms)
    client.post(LINK_BUFFER_URL, {"api_key": "buffer-key-1"}, format="json")
    refusal = {"json": {"data": {"createPost": {"message": "Image not found"}}}}
    platforms.set_route("POST", BUFFER_PATH, refusal)

    with pytest.raises(ProviderError, match="Image not found"):
        get_publisher("buffer").publish(
            SocialAccount.objects.first(), PostContent("C", b"", PUBLIC_POSTER)
        )


def test_buffer_cannot_be_given_a_poster_on_a_private_address(
    client, platforms, settings
):
    add_buffer_routes(platforms)
    client.post(LINK_BUFFER_URL, {"api_key": "buffer-key-1"}, format="json")
    account = SocialAccount.objects.first()
    # The stub server needs private addresses; a real server refuses them.
    settings.ALLOW_PRIVATE_PROVIDER_URLS = False
    local_poster = "http://localhost:8000/api/v1/public/posters/abc.png"

    with pytest.raises(ProviderError, match="PUBLIC_API_URL"):
        get_publisher("buffer").publish(account, PostContent("C", b"", local_poster))
