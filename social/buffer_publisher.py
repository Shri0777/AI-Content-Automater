"""Post through Buffer, which then posts to the networks the user connected.

Linking is simple: the user pastes a personal API key from Buffer
(Settings > API) and we find their channels; each channel becomes one linked
account. Buffer's API is GraphQL: every request is a POST of a query.

Buffer does not accept uploaded image files. It downloads the image from a
public address, so the poster is offered at a signed link
(studio/public_links.py) and PUBLIC_API_URL must be reachable from the
internet.

Docs (checked 2026-11-17): https://developers.buffer.com/llms-full.txt
(guides "Your First Post", "Posts & Scheduling" and "Hosting Media").
"""

from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from core import web
from core.errors import ProviderError
from social.publishers import Publisher, access_token_of, bearer, read_answer

ORGANIZATIONS_QUERY = "query { account { organizations { id name } } }"
CHANNELS_QUERY = """
query GetChannels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) { id name service }
}
"""
CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id } }
    ... on MutationError { message }
  }
}
"""
# Posts reach Buffer at their scheduled time (publishing/scheduled.py).
# Buffer needs a moment to download the poster before the post goes out.
SEND_AFTER = timedelta(minutes=2)


def ask_buffer(api_key, query, variables):
    """Send one GraphQL request and return its "data" part."""
    answer = web.post_json(
        settings.SOCIAL_API_URLS["buffer"],
        bearer(api_key),
        {"query": query, "variables": variables},
    )
    errors = answer.get("errors")
    if errors:
        raise ProviderError(f"Buffer refused the request: {errors[0].get('message')}")
    return read_answer(answer, ["data"], "Buffer")


def channel_to_account(channel, api_key):
    """Turn one Buffer channel into a found account."""
    service = channel.get("service", "")
    name = channel.get("name", "Channel")
    return {
        "external_id": read_answer(channel, ["id"], "Buffer"),
        "channel_name": name,
        "display_name": f"{name} ({service} via Buffer)",
        "network": service,
        "access_token": api_key,
        "expires_in": None,
        "scopes": "",
    }


def check_buffer_can_download(image_url):
    """Raise ProviderError if Buffer could not reach image_url."""
    try:
        web.check_address(image_url)
    except web.UnsafeAddress:
        host = urlsplit(image_url).hostname
        raise ProviderError(
            f"Buffer downloads the poster from this server, but {host} cannot be "
            "reached from the internet. Set PUBLIC_API_URL to a public address."
        ) from None


class BufferPublisher(Publisher):
    """Adds the post to a Buffer channel, to be sent two minutes later."""

    def find_channels(self, api_key):
        """Return every channel in every organisation the API key can see."""
        data = ask_buffer(api_key, ORGANIZATIONS_QUERY, {})
        accounts = []
        for organization in read_answer(data, ["account", "organizations"], "Buffer"):
            variables = {"organizationId": organization["id"]}
            data = ask_buffer(api_key, CHANNELS_QUERY, variables)
            channels = read_answer(data, ["channels"], "Buffer")
            for channel in channels:
                accounts.append(channel_to_account(channel, api_key))
        return accounts

    def publish(self, account, content):
        """Create the post in Buffer and return Buffer's post id."""
        check_buffer_can_download(content.image_url)
        send_at = timezone.now() + SEND_AFTER
        post_input = {
            "text": content.caption,
            "channelId": account.external_id,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": send_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "assets": [{"image": {"url": content.image_url}}],
        }
        data = ask_buffer(
            access_token_of(account), CREATE_POST_MUTATION, {"input": post_input}
        )
        result = read_answer(data, ["createPost"], "Buffer")
        if "message" in result:
            raise ProviderError(f"Buffer refused the post: {result['message']}")
        return read_answer(result, ["post", "id"], "Buffer")
