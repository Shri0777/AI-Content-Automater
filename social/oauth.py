"""Link accounts on platforms that use OAuth (X, LinkedIn, Facebook).

1. start_link: we save a LinkAttempt with a random "state" and a PKCE secret,
   and send the user to the platform's approval page.
2. The platform sends the user back to our callback with a code and the
   same state.
3. finish_link: we find the attempt by its state (once only, within ten
   minutes), swap the code for tokens and save the accounts.

The state stops other websites from linking their account to our user
(cross-site request forgery). PKCE proves that whoever swaps the code is
the one who started the attempt: we send a fingerprint of a secret first,
and the secret itself only when swapping the code.
"""

import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from core.crypto import decrypt_text, encrypt_text
from core.errors import AppError, ProviderError
from quotas.services import check_total_limit, count_total_items
from social.models import LinkAttempt
from social.platforms import is_ready_to_link, publisher_for
from social.services import PlatformNotReady, save_found_accounts

ATTEMPT_LIFETIME = timedelta(minutes=10)


class LinkFailed(AppError):
    """Raised when a link attempt is unknown, used already or too old."""

    code = "link_failed"
    title = "Link failed"


def fingerprint(text):
    """Return the SHA-256 fingerprint of text, as hex."""
    return hashlib.sha256(text.encode()).hexdigest()


def make_code_challenge(code_verifier):
    """Return the PKCE challenge (S256) for a secret code_verifier."""
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def callback_url(platform):
    """Return the address the platform sends the user back to."""
    return f"{settings.PUBLIC_API_URL}/api/v1/social/link/{platform}/callback/"


def start_link(user, platform):
    """Start linking an account; return the platform's approval page address."""
    publisher = get_publisher_for_oauth(user, platform)
    linked_count = count_total_items(user, "social_accounts")
    check_total_limit(user, "social_accounts", linked_count)
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(48)
    LinkAttempt.objects.create(
        user=user,
        platform=platform,
        state_hash=fingerprint(state),
        encrypted_code_verifier=encrypt_text(code_verifier),
    )
    challenge = make_code_challenge(code_verifier)
    return publisher.authorization_url(state, challenge, callback_url(platform))


def get_publisher_for_oauth(user, platform):
    """Return the platform's publisher as the user's app, or raise PlatformNotReady."""
    if platform not in settings.SOCIAL_APPS or not is_ready_to_link(platform, user):
        raise PlatformNotReady(
            f"Linking '{platform}' accounts needs a developer app. "
            "Save your app's id and secret first."
        )
    return publisher_for(user, platform)


def claim_attempt(platform, state):
    """Return the waiting attempt for state and mark it used, or raise LinkFailed."""
    attempt = LinkAttempt.objects.filter(
        state_hash=fingerprint(state),
        platform=platform,
        used_at=None,
        created_at__gte=timezone.now() - ATTEMPT_LIFETIME,
    ).first()
    if attempt is None:
        raise LinkFailed("This link attempt is unknown, used already or too old.")
    # Only one request can change used_at from empty, so a replayed callback
    # that arrives at the same moment gets 0 rows and fails.
    claimed = LinkAttempt.objects.filter(id=attempt.id, used_at=None).update(
        used_at=timezone.now()
    )
    if claimed == 0:
        raise LinkFailed("This link attempt was used already.")
    return attempt


def finish_link(platform, code, state):
    """Finish a link attempt and return the saved accounts."""
    attempt = claim_attempt(platform, state)
    publisher = get_publisher_for_oauth(attempt.user, platform)
    code_verifier = decrypt_text(attempt.encrypted_code_verifier)
    found = publisher.finish_link(code, code_verifier, callback_url(platform))
    return save_found_accounts(attempt.user, platform, found)


def result_page(platform, result, reason=""):
    """Return the frontend address that shows how linking went."""
    params = {"platform": platform, "result": result}
    if reason:
        params["reason"] = reason
    return f"{settings.FRONTEND_URL}/social/link-result?{urlencode(params)}"


def handle_callback(platform, params):
    """Finish linking from the platform's callback; return where to send the user."""
    if params.get("error"):
        return result_page(platform, "cancelled")
    try:
        finish_link(platform, params.get("code", ""), params.get("state", ""))
    except AppError as error:
        return result_page(platform, "error", error.code)
    except ProviderError:
        return result_page(platform, "error", "platform_error")
    return result_page(platform, "linked")
