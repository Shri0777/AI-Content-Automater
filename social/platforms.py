"""Facts about each social platform: limits, setup and its publisher class.

The rest of the code asks this file instead of checking platform names
itself, so adding a platform means changing this file and adding one
publisher class.
"""

from django.conf import settings

from demo.publisher import DemoPublisher
from social.buffer_publisher import BufferPublisher
from social.facebook_publisher import FacebookPublisher
from social.linkedin_publisher import LinkedInPublisher
from social.platform_apps import APP_PLATFORMS, app_keys_for
from social.x_publisher import XPublisher

PUBLISHER_CLASSES = {
    "demo": DemoPublisher,
    "buffer": BufferPublisher,
    "x": XPublisher,
    "linkedin": LinkedInPublisher,
    "facebook": FacebookPublisher,
}

# The longest caption each network accepts, in characters. X's limit is from
# its API reference; the others are from each platform's help pages and
# should be re-checked before going live. A network we do not know (for
# example a new one added to Buffer) gets the smallest limit, so a caption
# is never too long for it.
CAPTION_LIMITS = {
    "demo": 3000,
    "x": 280,
    "twitter": 280,
    "linkedin": 3000,
    "facebook": 63206,
    "instagram": 2200,
    "threads": 500,
    "mastodon": 500,
    "bluesky": 300,
}
SMALLEST_CAPTION_LIMIT = 280


def caption_limit_for(account):
    """Return the longest caption the account's network accepts."""
    network = account.network or account.platform
    return CAPTION_LIMITS.get(network, SMALLEST_CAPTION_LIMIT)


def get_publisher(platform, app=None):
    """Return the publisher for a platform, for example "x".

    app is the developer app to act as (see social/platform_apps.py); only
    X, LinkedIn and Facebook need one, to link accounts and refresh tokens.
    """
    publisher_class = PUBLISHER_CLASSES.get(platform)
    if publisher_class is None:
        raise ValueError(f"No publisher exists for the platform '{platform}'.")
    return publisher_class(app)


def publisher_for(user, platform):
    """Return the platform's publisher, acting as the user's developer app."""
    if platform in APP_PLATFORMS:
        return get_publisher(platform, app_keys_for(user, platform))
    return get_publisher(platform)


def publisher_for_account(account):
    """Return the publisher for a linked account, as its owner's app."""
    return publisher_for(account.user, account.platform)


def is_ready_to_link(platform, user):
    """Return True if the user can link an account on this platform right now."""
    if platform == "demo":
        return settings.DEMO_MODE
    if platform == "buffer":
        return True
    if platform not in APP_PLATFORMS:
        return False
    return bool(app_keys_for(user, platform)["client_id"])
