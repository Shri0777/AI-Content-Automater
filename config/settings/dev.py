"""Settings for running the project on your own computer.

Everything comes from base.py; this file only switches on debugging and
allows the refresh cookie over plain http on localhost.
"""

# Django settings files conventionally copy every value from the base file.
from config.settings.base import *  # noqa: F403

DEBUG = True
REFRESH_COOKIE_SECURE = False
