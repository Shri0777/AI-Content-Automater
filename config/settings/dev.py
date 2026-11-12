"""Settings for running the project on your own computer.

Everything comes from base.py. This file switches on debugging, allows the
refresh cookie over plain http on localhost, and turns on demo mode unless
DEMO_MODE=false is set, so the app works without any API keys.
"""

from config.env import read_bool

# Django settings files conventionally copy every value from the base file.
from config.settings.base import *  # noqa: F403

DEBUG = True
REFRESH_COOKIE_SECURE = False
DEMO_MODE = read_bool("DEMO_MODE", True)
