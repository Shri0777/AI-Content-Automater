"""Link, list and unlink a user's social accounts, and find their publisher."""

import uuid

from django.conf import settings

from core.errors import AppError
from demo.publisher import DemoPublisher
from quotas.services import check_total_limit, count_total_items
from social.models import SocialAccount


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


def get_accounts(user):
    """Return the user's linked accounts, oldest first."""
    return SocialAccount.objects.filter(user=user)


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
        display_name=f"Demo account {number}",
        external_id=f"demo-{uuid.uuid4().hex[:12]}",
    )


def unlink_account(user, account_id):
    """Remove one of the user's linked accounts."""
    account = SocialAccount.objects.filter(id=account_id, user=user).first()
    if account is None:
        raise SocialAccountNotFound("That social account does not exist.")
    account.delete()


def count_accounts_needing_attention(user):
    """Return how many of the user's accounts must be reconnected."""
    return SocialAccount.objects.filter(user=user, status="needs_reauth").count()


def get_publisher(platform):
    """Return the publisher for a platform, for example "demo"."""
    if platform == "demo":
        return DemoPublisher()
    raise ValueError(f"No publisher exists for the platform '{platform}'.")
