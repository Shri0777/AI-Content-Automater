"""The real work behind accounts: invite codes, registration and login tokens.

Views call these functions; these functions never deal with HTTP details
such as cookies or headers.
"""

import hashlib
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import InviteCode, RecoveryCode, User
from core.errors import AppError

RECOVERY_CODES_PER_USER = 8
# Letters and digits for recovery codes. Look-alikes (0/O, 1/I/L) are left out
# because people copy these codes onto paper and type them back later.
RECOVERY_CODE_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


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


class RecoveryFailed(AppError):
    """Raised when an email and recovery code do not match."""

    status = 400
    code = "recovery_failed"
    title = "Recovery failed"


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
    """Create a new account and its recovery codes.

    Follows the REGISTRATION_MODE setting. Returns the user and their
    recovery codes, which are shown to the user only this once.
    """
    if settings.REGISTRATION_MODE == "closed":
        raise RegistrationClosed("New accounts cannot be created right now.")
    # Everything happens together: if the invite code is refused, the new
    # user and their recovery codes are removed again.
    with transaction.atomic():
        user = User.objects.create_user(email=email, password=password)
        if settings.REGISTRATION_MODE == "invite":
            use_invite_code(invite_code, user)
        recovery_codes = create_recovery_codes(user)
    return {"user": user, "recovery_codes": recovery_codes}


def make_recovery_code():
    """Return one new recovery code for a person to write down and keep.

    A code looks like K7QX-M2VD-9HTP: 12 random characters in 3 groups.
    """
    groups = []
    for _ in range(3):
        group = ""
        for _ in range(4):
            # secrets (not random) is the module made for security uses.
            group = group + secrets.choice(RECOVERY_CODE_LETTERS)
        groups.append(group)
    return "-".join(groups)


def normalize_recovery_code(code):
    """Return a code the way we check it: no spaces or dashes, upper case."""
    return code.replace("-", "").replace(" ", "").upper()


def create_recovery_codes(user):
    """Replace the user's recovery codes with 8 new ones and return them."""
    codes = []
    with transaction.atomic():
        RecoveryCode.objects.filter(user=user).delete()
        for _ in range(RECOVERY_CODES_PER_USER):
            code = make_recovery_code()
            code_hash = make_password(normalize_recovery_code(code))
            RecoveryCode.objects.create(user=user, code_hash=code_hash)
            codes.append(code)
    return codes


def find_matching_code(user, typed_code):
    """Return the user's unused RecoveryCode that matches typed_code, or None."""
    normalized = normalize_recovery_code(typed_code)
    for saved_code in RecoveryCode.objects.filter(user=user, used_at=None):
        if check_password(normalized, saved_code.code_hash):
            return saved_code
    return None


def log_out_everywhere(user):
    """Cancel every refresh token the user has, on every device."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def recover_account(email, typed_code, new_password):
    """Reset a forgotten password with a recovery code; return codes left."""
    failure = RecoveryFailed("That email and recovery code do not match.")
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        # Spend as long as a real check would, so the answer's timing does
        # not reveal whether the email has an account.
        make_password(typed_code)
        raise failure
    with transaction.atomic():
        saved_code = find_matching_code(user, typed_code)
        if saved_code is None:
            raise failure
        # Claim the code with one UPDATE that only matches unused codes, so
        # two requests racing with the same code cannot both succeed.
        claimed_rows = RecoveryCode.objects.filter(
            id=saved_code.id, used_at=None
        ).update(used_at=timezone.now())
        if claimed_rows == 0:
            raise failure
        user.set_password(new_password)
        user.save(update_fields=["password"])
        log_out_everywhere(user)
    return RecoveryCode.objects.filter(user=user, used_at=None).count()


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
