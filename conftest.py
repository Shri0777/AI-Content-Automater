"""Shared test helpers that every test in the project can use.

pytest finds this file automatically. Anything defined here as a fixture
can be requested by a test simply by naming it as a parameter.
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from tests.stub_server import StubServer


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Empty the cache so one test's rate-limit counters never affect another."""
    cache.clear()


@pytest.fixture(autouse=True)
def temporary_media_folder(settings, tmp_path):
    """Save generated files (such as posters) in a throwaway folder."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def api_client():
    """Return a client that can call the API like a browser or app would."""
    return APIClient()


@pytest.fixture
def stub_server(request, settings):
    """A running fake provider on this machine (see tests/stub_server.py).

    It lives on 127.0.0.1, so this fixture also allows private addresses,
    which the SSRF rules otherwise refuse.
    """
    settings.ALLOW_PRIVATE_PROVIDER_URLS = True
    server = StubServer()
    server.start()
    request.addfinalizer(server.stop)
    return server
