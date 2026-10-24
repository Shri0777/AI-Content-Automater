"""Base Django settings for the AI Content Automater project."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent

if not os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith(".production"):
    load_dotenv(BASE_DIR / ".env")


def get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    """Read an environment value and fail clearly when a required value is empty."""
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value or ""


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_list_env(name: str, default: str = "") -> list[str]:
    raw_value = os.environ.get(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


SECRET_KEY = get_env("SECRET_KEY", required=True)
DEBUG = get_bool_env("DEBUG", default=False)
ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "django_celery_beat",
    # Project apps
    "users",
    "content",
    "research",
    "ai_providers",
    "frontend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "content_automater.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "content_automater.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_env("DB_NAME", "ai_content_automater_dev"),
        "USER": get_env("DB_USER", "postgres"),
        "PASSWORD": get_env("DB_PASSWORD", ""),
        "HOST": get_env("DB_HOST", "localhost"),
        "PORT": get_env("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication settings
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/"

# AI Services Canonical Configuration (Phase 3)
# AI Provider Configuration (Phase 3)
TEXT_API_KEY = os.getenv("TEXT_API_KEY", "")
TEXT_PROVIDER = os.getenv("TEXT_PROVIDER", "auto")  # openai, nvidia, anthropic, or auto
TEXT_API_BASE_URL = os.getenv("TEXT_API_BASE_URL", "")  # Optional custom endpoint
TEXT_MODEL = os.getenv("TEXT_MODEL", "")  # Optional model override

IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "")
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "auto")  # nvidia_flux or auto
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "black-forest-labs/flux-3-image-klein")

CREDENTIAL_ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY", None)
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", CREDENTIAL_ENCRYPTION_KEY)

# Buffer Publishing Configuration (Phase 6 - Official GraphQL API)
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "")
BUFFER_API_URL = os.getenv("BUFFER_API_URL", "https://api.buffer.com")
BUFFER_API_BASE_URL = os.getenv("BUFFER_API_BASE_URL", BUFFER_API_URL)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ============================================================================
# Celery Configuration (Background Tasks)
# ============================================================================

CELERY_BROKER_URL = get_env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = get_env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes soft limit

# Celery Beat Schedule (Periodic Tasks)
CELERY_BEAT_SCHEDULE = {
    'schedule-due-campaigns': {
        'task': 'content.tasks.schedule_due_campaigns',
        'schedule': 60.0,  # Every minute
    },
    'reconcile-ambiguous-publications': {
        'task': 'content.tasks.reconcile_ambiguous_publications',
        'schedule': 300.0,  # Every 5 minutes
    },
}


# ============================================================================
# Media Files (User Uploads)
# ============================================================================

# Default local storage (used when R2 is not configured)
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# -----------------------------------------------------------------------------
# Cloudflare R2 Storage (Optional - enables public HTTPS media URLs for Buffer)
# -----------------------------------------------------------------------------
# When all R2_* environment variables are set and MEDIA_STORAGE=r2,
# Django uses S3-compatible R2 storage with a custom public domain.
# This provides stable, publicly reachable HTTPS URLs required by Buffer.
#
# Required env vars for R2:
#   R2_ACCOUNT_ID           Cloudflare account ID
#   R2_ACCESS_KEY_ID        R2 API access key ID
#   R2_SECRET_ACCESS_KEY    R2 API secret access key
#   R2_BUCKET_NAME          R2 bucket name
#   R2_PUBLIC_DOMAIN        Custom domain for public access (e.g., media.example.com)
#   MEDIA_STORAGE=r2        Explicit opt-in to enable R2 backend
#
# The bucket should be PRIVATE. Public access is granted ONLY via the custom
# domain configured in Cloudflare (R2_PUBLIC_DOMAIN -> R2 bucket).
# This keeps the origin secure while providing clean HTTPS URLs.

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")
R2_PUBLIC_DOMAIN = os.getenv("R2_PUBLIC_DOMAIN", "")
MEDIA_STORAGE = os.getenv("MEDIA_STORAGE", "").strip().lower()  # 'r2' or ''

_R2_CONFIGURED = all([
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_PUBLIC_DOMAIN,
    MEDIA_STORAGE == "r2",
])

if _R2_CONFIGURED:
    INSTALLED_APPS += ["storages"]

    # S3-compatible endpoint for Cloudflare R2
    AWS_S3_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_S3_REGION_NAME = "auto"
    AWS_S3_SIGNATURE_VERSION = "s3v4"

    # Custom domain for public HTTPS URLs (e.g., https://media.example.com/)
    AWS_S3_CUSTOM_DOMAIN = R2_PUBLIC_DOMAIN
    AWS_S3_URL_PROTOCOL = "https:"

    # Security: private bucket, no public ACLs, no query-string auth on public URLs
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False

    # Cache control for generated images (adjust as needed)
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "public, max-age=31536000, immutable",
    }

    # Use S3Boto3Storage for media files
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    # MEDIA_URL uses the custom domain for public HTTPS URLs
    MEDIA_URL = f"https://{R2_PUBLIC_DOMAIN}/"
