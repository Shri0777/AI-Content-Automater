"""Development settings for AI Content Automater."""

from .base import *  # noqa: F403


DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INTERNAL_IPS = ["127.0.0.1"]

# Email configuration for development (console backend)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@aicontentautomater.local'
PASSWORD_RESET_TIMEOUT = 1800  # 30 minutes
