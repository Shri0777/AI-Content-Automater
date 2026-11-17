"""Production refuses to start with missing or unencrypted addresses."""

import os
import subprocess
import sys

import pytest

GOOD_ENVIRONMENT = {
    "DJANGO_SETTINGS_MODULE": "config.settings.prod",
    "DJANGO_SECRET_KEY": "test-only-not-secret-3f9a7c1e5b2d8a6f4c0e9b7d5a3f1c8e",
    "ENCRYPTION_KEY": "4kuHz3t5x4cXJ0G6Lq8V9pWmRbN2sYfT7aDcEgHiJkM=",
    "DJANGO_ALLOWED_HOSTS": "api.example.com",
    "CORS_ALLOWED_ORIGINS": "https://app.example.com",
    "PUBLIC_API_URL": "https://api.example.com",
    "FRONTEND_URL": "https://app.example.com",
}


def load_production_settings(changes):
    """Load production settings in a fresh Python with some values changed."""
    environment = dict(os.environ)
    environment.update(GOOD_ENVIRONMENT)
    for name, value in changes.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    code = "import django; django.setup(); print('started')"
    return subprocess.run(  # noqa: S603 - fixed command, our own code
        [sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_starts_with_real_https_addresses():
    result = load_production_settings({})

    assert result.returncode == 0, result.stderr
    assert "started" in result.stdout


@pytest.mark.parametrize(
    "name, value",
    [
        ("PUBLIC_API_URL", None),
        ("PUBLIC_API_URL", "http://api.example.com"),
        ("FRONTEND_URL", "http://localhost:5173"),
        ("CORS_ALLOWED_ORIGINS", None),
        ("CORS_ALLOWED_ORIGINS", "http://localhost:3000"),
    ],
)
def test_production_refuses_a_missing_or_unencrypted_address(name, value):
    result = load_production_settings({name: value})

    assert result.returncode != 0
    assert name in result.stderr
