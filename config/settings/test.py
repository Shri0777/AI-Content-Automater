"""Settings used when the automated tests run.

They match development, but use a fast password hasher so tests that
create many users stay quick. The hasher is unsafe and is never used outside
tests.
"""

# Django settings files conventionally copy every value from the base file.
from config.settings.base import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
