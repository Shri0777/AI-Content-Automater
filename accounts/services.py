"""The real work behind accounts: invite codes, registration and login tokens.

Views call these functions; these functions never deal with HTTP details
such as cookies or headers.
"""

import hashlib
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import InviteCode, User
from core.errors import AppError


class RegistrationClosed(AppError):
    """Raised when nobody may create an account right now."""

    status = 403
    code = "registration_closed"
    title = "Registration closed"


class InvalidInviteCode(AppError):
    """Raised when an invite code is missing, wrong or already used."""

    status = 400
    code = "invalid_invite_code"
    title = "Invalid invite code"


class InvalidCredentials(AppError):
    """Raised when an email and password do not match an account."""

    status = 401
    code = "invalid_credentials"
    title = "Login failed"


class NotLoggedIn(AppError):
    """Raised when a refresh token is missing, expired or already used."""

    status = 401
    code = "not_logged_in"
    title = "Not logged in"


def hash_code(code):
    """Return the SHA-256 fingerprint of a code. We store this, not the code."""
    return hashlib.sha256(code.encode()).hexdigest()


def create_invite_codes(count):
    """Create count new invite codes and return them as plain text (shown once)."""
    codes = []
    # "_" is the usual name for a loop counter we do not need.
    for _ in range(count):
        code = secrets.token_urlsafe(12)
        InviteCode.objects.create(code_hash=hash_code(code))
        codes.append(code)
    return codes


def use_invite_code(code, user):
    """Mark an unused invite code as used by user, or raise InvalidInviteCode."""
    if not code:
        raise InvalidInviteCode("An invite code is needed to create an account.")
    # A single UPDATE that only matches unused codes. If two people try the
    # same code at once, only one UPDATE can change the row.
    updated_rows = InviteCode.objects.filter(
        code_hash=hash_code(code), used_by=None
    ).update(used_by=user, used_at=timezone.now())
    if updated_rows == 0:
        raise InvalidInviteCode("This invite code is not valid or was already used.")


def register_user(email, password, invite_code):
    """Create a new account, following the REGISTRATION_MODE setting."""
    if settings.REGISTRATION_MODE == "closed":
        raise RegistrationClosed("New accounts cannot be created right now.")
    # Creating the user and using the code happen together: if the code is
    # refused, the new user is removed again.
    with transaction.atomic():
        user = User.objects.create_user(email=email, password=password)
        if settings.REGISTRATION_MODE == "invite":
            use_invite_code(invite_code, user)
    return user


def log_in(request, email, password):
    """Check the email and password and return a new pair of login tokens."""
    user = authenticate(request, email=email, password=password)
    if user is None:
        raise InvalidCredentials("The email or password is incorrect.")
    refresh = RefreshToken.for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    return {"user": user, "access": str(refresh.access_token), "refresh": str(refresh)}


def refresh_login(refresh_token):
    """Swap a refresh token for a new access token and a new refresh token.

    The old refresh token is cancelled, so it can never be used again.
    """
    serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
    try:
        serializer.is_valid(raise_exception=True)
    except TokenError:
        raise NotLoggedIn("Your login has expired. Please log in again.") from None
    return serializer.validated_data


def log_out(refresh_token):
    """Cancel a refresh token so it can never be used again."""
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError:
        # The token was already expired or cancelled; nothing left to do.
        return
