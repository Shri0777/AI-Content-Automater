"""Settings used when the automated tests run.

They match development, with three changes:
- a fast password hasher, so tests that create many users stay quick
  (it is unsafe and never used outside tests);
- demo mode, so tests use the built-in fake providers;
- background jobs run immediately inside the test instead of being sent to
  a separate worker. The end-to-end walkthrough checks the real worker;
- an in-memory cache instead of Redis.
"""

# Django settings files conventionally copy every value from the base file.
from config.settings.base import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DEMO_MODE = True
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Each test run gets its own in-memory cache instead of Redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
