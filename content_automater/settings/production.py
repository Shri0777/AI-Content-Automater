"""Production settings for AI Content Automater."""

from .base import *  # noqa: F403
from .base import get_env, get_list_env
from django.core.exceptions import ImproperlyConfigured


DEBUG = False
SECRET_KEY = get_env("SECRET_KEY", required=True)
ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set for production.")

DATABASES["default"].update(  # noqa: F405
    {
        "NAME": get_env("DB_NAME", required=True),
        "USER": get_env("DB_USER", required=True),
        "PASSWORD": get_env("DB_PASSWORD", required=True),
        "HOST": get_env("DB_HOST", required=True),
        "PORT": get_env("DB_PORT", required=True),
    }
)


# Provider credentials must remain decryptable across process restarts.
CREDENTIAL_ENCRYPTION_KEY = get_env('CREDENTIAL_ENCRYPTION_KEY') or get_env('FIELD_ENCRYPTION_KEY')
if not CREDENTIAL_ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        'CREDENTIAL_ENCRYPTION_KEY (or FIELD_ENCRYPTION_KEY) must be set in production.'
    )

SESSION_COOKIE_SECURE = get_env('SESSION_COOKIE_SECURE', 'true').lower() in {'1', 'true', 'yes', 'on'}
CSRF_COOKIE_SECURE = get_env('CSRF_COOKIE_SECURE', 'true').lower() in {'1', 'true', 'yes', 'on'}
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_SSL_REDIRECT = get_env('SECURE_SSL_REDIRECT', 'true').lower() in {'1', 'true', 'yes', 'on'}
