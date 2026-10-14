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
