"""Settings for production.

Production refuses to start unless the real secrets are provided as
environment variables, and it switches on Django's HTTPS protections.
"""

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
