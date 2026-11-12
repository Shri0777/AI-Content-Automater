"""Small helpers that read settings from environment variables.

Settings such as passwords and database addresses should not be written in
the code. They come from environment variables instead. These helpers read
one variable each and turn it into the type we need (text, number, yes/no,
or a list).
"""

import os

from django.core.exceptions import ImproperlyConfigured

TRUE_WORDS = ["1", "true", "yes", "on"]


def read_text(name, default=None):
    """Return an environment variable as text, or the default if it is unset."""
    value = os.environ.get(name, "")
    if value.strip() == "":
        return default
    return value.strip()


def read_bool(name, default):
    """Return an environment variable as True or False."""
    value = read_text(name)
    if value is None:
        return default
    return value.lower() in TRUE_WORDS


def read_int(name, default):
    """Return an environment variable as a whole number."""
    value = read_text(name)
    if value is None:
        return default
    return int(value)


def read_list(name, default):
    """Return a comma-separated environment variable as a list of text."""
    value = read_text(name)
    if value is None:
        return default
    items = []
    for item in value.split(","):
        if item.strip() != "":
            items.append(item.strip())
    return items


def require_text(name):
    """Return an environment variable, and stop with a clear error if missing."""
    value = read_text(name)
    if value is None:
        raise ImproperlyConfigured(f"The environment variable {name} must be set.")
    return value
