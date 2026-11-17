"""Keep each linked account's token working: save, refresh and warn.

Tokens are refreshed shortly before they expire, both before every post and
by a background job every 30 minutes. Some platforms (X, Buffer) give a
refresh token that works only once, so two workers must never refresh the
same account at the same moment: refresh_account() locks the account's row
while it refreshes, and the second worker then sees the fresh token.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.crypto import encrypt_text
from core.errors import ProviderBusy, ProviderKeyRejected
from notifications.services import notify
from social.models import SocialAccount
from social.platforms import get_publisher

# Before a post: refresh if the token ends within this time.
REFRESH_BEFORE_POSTING = timedelta(minutes=10)
# The background job runs every 30 minutes, so it looks a little further.
REFRESH_IN_BACKGROUND = timedelta(minutes=45)
# For tokens that cannot be refreshed (LinkedIn): warn this long before.
WARN_BEFORE_EXPIRY = timedelta(days=7)


def expiry_time(expires_in):
    """Return when a token given expires_in seconds from now stops working."""
    if expires_in is None:
        return None
    return timezone.now() + timedelta(seconds=int(expires_in))


def store_tokens(account, tokens):
    """Copy new tokens onto account (encrypted). The caller saves it."""
    account.encrypted_token = encrypt_text(tokens["access_token"])
    if tokens.get("refresh_token"):
        account.encrypted_refresh_token = encrypt_text(tokens["refresh_token"])
    account.token_expires_at = expiry_time(tokens.get("expires_in"))
    if tokens.get("scopes"):
        account.scopes = tokens["scopes"]


def expires_within(account, time_left):
    """Return True if the account's token stops working within time_left."""
    if account.token_expires_at is None:
        return False
    return account.token_expires_at <= timezone.now() + time_left


def mark_needs_reauth(account, reason):
    """Mark the account as needing a new link, and tell its owner once."""
    account.status = "needs_reauth"
    account.last_error = reason
    account.save(update_fields=["status", "last_error"])
    notify(
        account.user,
        "account_needs_reauth",
        f"Reconnect {account.display_name}: {reason}",
        related=account,
        dedupe_key=f"reauth:{account.id}",
    )


def refresh_locked_account(account):
    """Refresh an account whose row the caller has locked."""
    try:
        tokens = get_publisher(account.platform).refresh_tokens(account)
    except ProviderKeyRejected:
        mark_needs_reauth(account, "The platform no longer accepts this link.")
        return
    if tokens is None:
        if expires_within(account, timedelta(0)):
            mark_needs_reauth(account, "The link has expired.")
        return
    store_tokens(account, tokens)
    account.save()


def refresh_account(account_id, time_left):
    """Refresh the account's token if it stops working within time_left.

    Returns the account as it is afterwards. ProviderBusy is raised on, so
    the caller can try again later; nothing is changed in that case.
    """
    with transaction.atomic():
        # select_for_update() locks this row until the transaction ends, so
        # a second worker waits here instead of reusing an old refresh token.
        account = (
            SocialAccount.objects.select_for_update()
            .select_related("user")
            .get(id=account_id)
        )
        if account.status == "active" and expires_within(account, time_left):
            refresh_locked_account(account)
    return account


def warn_if_expiring(account):
    """Warn the owner a week before a token that cannot be refreshed ends."""
    if account.encrypted_refresh_token:
        return
    if not expires_within(account, WARN_BEFORE_EXPIRY):
        return
    end_date = timezone.localdate(account.token_expires_at)
    notify(
        account.user,
        "account_needs_reauth",
        f"{account.display_name} stays connected until {end_date}. "
        "Link it again before then to keep posting.",
        related=account,
        dedupe_key=f"expiry-warning:{account.id}:{end_date}",
    )


def refresh_expiring_accounts():
    """Refresh or warn about every active account whose token ends soon.

    Returns how many accounts were checked. An account whose platform is
    busy is skipped and tried again on the next run.
    """
    accounts = SocialAccount.objects.filter(
        status="active",
        token_expires_at__isnull=False,
        token_expires_at__lte=timezone.now() + WARN_BEFORE_EXPIRY,
    )
    checked = 0
    for account in accounts:
        try:
            account = refresh_account(account.id, REFRESH_IN_BACKGROUND)
        except ProviderBusy:
            continue
        if account.status == "active":
            warn_if_expiring(account)
        checked = checked + 1
    return checked
