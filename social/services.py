"""Link, list and unlink a user's social accounts.

Linking through OAuth (X, LinkedIn, Facebook) is in social/oauth.py; both it
and Buffer save accounts with save_found_accounts() below.
"""

import uuid

from django.conf import settings
from django.db import transaction

from core.errors import AppError, ProviderError, ProviderKeyRejected
from quotas.services import check_total_limit, count_total_items
from social.buffer_publisher import BufferPublisher
from social.models import SocialAccount
from social.platforms import get_publisher
from social.tokens import store_tokens


class SocialAccountNotFound(AppError):
    """Raised when an account does not exist or belongs to someone else."""

    status = 404
    code = "not_found"
    title = "Not found"


class DemoModeOff(AppError):
    """Raised when someone uses a demo-only feature while demo mode is off."""

    status = 400
    code = "demo_mode_off"
    title = "Demo mode is off"


class PlatformNotReady(AppError):
    """Raised for a platform this server has not been set up to link."""

    status = 400
    code = "platform_not_ready"
    title = "Platform not available"


class PlatformRefused(AppError):
    """Raised when a platform refuses to link an account."""

    status = 400
    code = "platform_refused"
    title = "The platform refused"


def get_accounts(user):
    """Return the user's linked accounts, oldest first."""
    return SocialAccount.objects.filter(user=user)


def save_found_account(user, platform, found):
    """Create or update one linked account from a found account dict."""
    account = SocialAccount.objects.filter(
        user=user, platform=platform, external_id=found["external_id"]
    ).first()
    if account is None:
        check_total_limit(
            user, "social_accounts", count_total_items(user, "social_accounts")
        )
        account = SocialAccount(
            user=user, platform=platform, external_id=found["external_id"]
        )
    account.display_name = found["display_name"][:200]
    account.network = found["network"]
    account.status = "active"
    account.last_error = ""
    store_tokens(account, found)
    account.save()
    return account


def save_found_accounts(user, platform, found_accounts):
    """Save every found account. If one breaks a limit, none are saved."""
    saved = []
    with transaction.atomic():
        for found in found_accounts:
            saved.append(save_found_account(user, platform, found))
    return saved


def link_buffer_accounts(user, api_key, channel_ids):
    """Link the Buffer channels the API key can see (or only channel_ids)."""
    try:
        channels = BufferPublisher().find_channels(api_key)
    except ProviderKeyRejected:
        raise PlatformRefused("Buffer did not accept this API key.") from None
    except ProviderError as error:
        raise PlatformRefused(str(error)) from None
    if channel_ids:
        channels = [found for found in channels if found["external_id"] in channel_ids]
    if not channels:
        raise PlatformRefused("No Buffer channels were found for this API key.")
    return save_found_accounts(user, "buffer", channels)


def link_demo_account(user):
    """Link a new account on the fake demo network and return it."""
    if not settings.DEMO_MODE:
        raise DemoModeOff("The demo network only works when DEMO_MODE is on.")
    linked_count = count_total_items(user, "social_accounts")
    check_total_limit(user, "social_accounts", linked_count)
    number = linked_count + 1
    return SocialAccount.objects.create(
        user=user,
        platform="demo",
        network="demo",
        display_name=f"Demo account {number}",
        external_id=f"demo-{uuid.uuid4().hex[:12]}",
    )


def unlink_account(user, account_id):
    """Cancel the account's tokens at the platform (where possible), then remove it.

    If the platform cannot be reached, the account is still removed: the
    user asked for it, and our copy of the tokens is deleted either way.
    """
    account = SocialAccount.objects.filter(id=account_id, user=user).first()
    if account is None:
        raise SocialAccountNotFound("That social account does not exist.")
    if account.encrypted_token:
        try_to_revoke(account)
    account.delete()


def try_to_revoke(account):
    """Ask the platform to cancel the account's tokens; return True if it did."""
    try:
        get_publisher(account.platform).revoke(account)
    except ProviderError:
        return False
    return True


def count_accounts_needing_attention(user):
    """Return how many of the user's accounts must be reconnected."""
    return SocialAccount.objects.filter(user=user, status="needs_reauth").count()
