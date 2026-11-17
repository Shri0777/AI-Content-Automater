"""Settings for production.

Production refuses to start unless the real secrets are provided as
environment variables, and it switches on Django's HTTPS protections.
"""

from django.core.exceptions import ImproperlyConfigured

from config.env import read_bool, read_int, require_text

# Django settings files conventionally copy every value from the base file.
from config.settings.base import *  # noqa: F403

DEBUG = False
SECRET_KEY = require_text("DJANGO_SECRET_KEY")
ENCRYPTION_KEY = require_text("ENCRYPTION_KEY")
ALLOWED_HOSTS = require_text("DJANGO_ALLOWED_HOSTS").split(",")

# Only talk to browsers over HTTPS.
SECURE_SSL_REDIRECT = read_bool("SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = read_int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
REFRESH_COOKIE_SECURE = True


def require_https_address(name):
    """Return an environment variable that must be an https:// address."""
    value = require_text(name).rstrip("/")
    if not value.startswith("https://"):
        raise ImproperlyConfigured(f"{name} must start with https:// in production.")
    return value


# No localhost defaults in production: the frontend that may call the API,
# where platforms send users back after linking, and where Buffer downloads
# posters must all be the real, encrypted addresses.
CORS_ALLOWED_ORIGINS = []
for origin in require_text("CORS_ALLOWED_ORIGINS").split(","):
    if not origin.strip().startswith("https://"):
        raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be https:// addresses.")
    CORS_ALLOWED_ORIGINS.append(origin.strip())
PUBLIC_API_URL = require_https_address("PUBLIC_API_URL")
FRONTEND_URL = require_https_address("FRONTEND_URL")
