"""Each user's own developer app for X, LinkedIn and Facebook.

Linking an account directly needs an app registered on the platform's
developer site. Users save their own app's id and secret here (the secret is
stored encrypted). The app in the server's .env (settings.SOCIAL_APPS), if
the operator set one, is used only for users who have not saved their own.
"""

from django.conf import settings
from django.db import transaction

from core.crypto import decrypt_text, encrypt_text
from core.errors import AppError
from social.models import APP_PLATFORM_CHOICES, PlatformApp

APP_PLATFORMS = [platform for platform, _name in APP_PLATFORM_CHOICES]


class PlatformAppNotFound(AppError):
    """Raised for a platform that takes no app, or an app the user never saved."""

    status = 404
    code = "platform_app_not_found"
    title = "Developer app not found"


def check_takes_an_app(platform):
    """Raise PlatformAppNotFound unless the platform is linked with an app."""
    if platform not in APP_PLATFORMS:
        raise PlatformAppNotFound(f"'{platform}' does not use a developer app.")


@transaction.atomic
def save_app(user, platform, client_id, client_secret):
    """Save (or replace) the user's app for a platform and return it."""
    check_takes_an_app(platform)
    app, _created = PlatformApp.objects.update_or_create(
        user=user,
        platform=platform,
        defaults={
            "client_id": client_id,
            "encrypted_client_secret": encrypt_text(client_secret),
        },
    )
    return app


def list_apps(user):
    """Return the apps the user has saved."""
    return PlatformApp.objects.filter(user=user)


def delete_app(user, platform):
    """Remove the user's app for a platform, or raise PlatformAppNotFound."""
    deleted, _details = PlatformApp.objects.filter(
        user=user, platform=platform
    ).delete()
    if deleted == 0:
        raise PlatformAppNotFound(f"You have not saved an app for '{platform}'.")


def app_keys_for(user, platform):
    """Return {"client_id", "client_secret"} to use for a user on a platform.

    The user's own app comes first, then the server's. Both values are empty
    when there is neither, which means the platform cannot be linked.
    """
    saved = PlatformApp.objects.filter(user=user, platform=platform).first()
    if saved is not None:
        return {
            "client_id": saved.client_id,
            "client_secret": decrypt_text(saved.encrypted_client_secret),
        }
    server_app = settings.SOCIAL_APPS.get(platform, {})
    return {
        "client_id": server_app.get("client_id", ""),
        "client_secret": server_app.get("client_secret", ""),
    }


def has_saved_app(user, platform):
    """Return True if the user saved their own app for the platform."""
    return PlatformApp.objects.filter(user=user, platform=platform).exists()
