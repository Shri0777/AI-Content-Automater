"""Settings shared by every environment (development, tests and production).

Values that change between environments are read from environment variables
with the helpers in config/env.py. Development-only defaults are clearly
marked; production (config/settings/prod.py) refuses to start without the
real values.
"""

from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab

from config.env import read_bool, read_int, read_list, read_text

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Development-only default. Production must set DJANGO_SECRET_KEY.
SECRET_KEY = read_text("DJANGO_SECRET_KEY", "dev-only-insecure-secret-key-change-me")
DEBUG = False
ALLOWED_HOSTS = read_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "core",
    "accounts",
    "quotas",
    "notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# The database. Development defaults match docker-compose.yml (port 5433).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": read_text("POSTGRES_DB", "ai_content_automator"),
        "USER": read_text("POSTGRES_USER", "automator"),
        "PASSWORD": read_text("POSTGRES_PASSWORD", "automator-dev-password"),
        "HOST": read_text("POSTGRES_HOST", "localhost"),
        "PORT": read_int("POSTGRES_PORT", 5433),
    }
}

# Users log in with their email address (see accounts/models.py).
AUTH_USER_MODEL = "accounts.User"

VALIDATORS_MODULE = "django.contrib.auth.password_validation."
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": VALIDATORS_MODULE + "UserAttributeSimilarityValidator"},
    {"NAME": VALIDATORS_MODULE + "MinimumLengthValidator"},
    {"NAME": VALIDATORS_MODULE + "CommonPasswordValidator"},
    {"NAME": VALIDATORS_MODULE + "NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The REST API. Every endpoint needs a logged-in user unless it says otherwise.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.errors.problem_details_handler",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "120/minute", "auth": "10/minute"},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AI Content Automator API",
    "DESCRIPTION": "Finds news, makes posters with AI, reviews them and posts them.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Login tokens. The short-lived access token travels in the Authorization
# header; the long-lived refresh token lives in an httpOnly cookie (ADR-009).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth/"
REFRESH_COOKIE_SECURE = read_bool("REFRESH_COOKIE_SECURE", True)
REFRESH_COOKIE_SAMESITE = "Lax"
# Requests that use the refresh cookie must also send this header. A plain
# form on another website cannot add custom headers, so this blocks
# cross-site request forgery against the cookie.
REQUIRED_AUTH_HEADER = "X-Requested-By"

# Which frontend websites may call this API with cookies.
CORS_ALLOWED_ORIGINS = read_list(
    "CORS_ALLOWED_ORIGINS", ["http://localhost:3000", "http://localhost:5173"]
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "idempotency-key",
    "x-requested-by",
]

# Who may create an account: "invite" (default), "open" or "closed".
REGISTRATION_MODE = read_text("REGISTRATION_MODE", "invite")

# Key used to encrypt saved API keys and tokens. Development-only default;
# production must set ENCRYPTION_KEY to its own secret key.
ENCRYPTION_KEY = read_text(
    "ENCRYPTION_KEY", "Z6DcUdGvq7hahOLqQS_y74vpYJFRZ78viVdYOCJC9ZQ="
)

# Background jobs. Development default matches docker-compose.yml (port 6380).
CELERY_BROKER_URL = read_text("CELERY_BROKER_URL", "redis://localhost:6380/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

# Jobs that run on a timetable. Every "task" must name a registered task;
# tests/test_celery_setup.py checks this.
CELERY_BEAT_SCHEDULE = {
    "delete-old-notifications": {
        "task": "notifications.tasks.delete_old_notifications_task",
        "schedule": crontab(hour=3, minute=0),
    },
}
