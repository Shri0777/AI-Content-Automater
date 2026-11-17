"""Rate limits really refuse too many requests, in the standard error shape."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

LOW_LIMITS = {
    "DEFAULT_THROTTLE_RATES": {
        "user": "3/minute",
        "auth": "10/minute",
        "credential_test": "10/minute",
    }
}


@pytest.fixture
def low_limits(monkeypatch):
    """Lower the general limit to 3 requests a minute for one test.

    Django REST framework copies the rates onto its throttle class when it
    is first imported, so changing settings later has no effect; the class
    value is replaced instead (and put back after the test).
    """
    monkeypatch.setattr(
        SimpleRateThrottle, "THROTTLE_RATES", LOW_LIMITS["DEFAULT_THROTTLE_RATES"]
    )
    cache.clear()


@pytest.fixture
def client(api_client, db):
    """A logged-in API client."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    api_client.force_authenticate(user)
    return api_client


def test_too_many_requests_from_one_user_are_refused(client, low_limits):
    statuses = []
    for _ in range(4):
        statuses.append(client.get("/api/v1/me/").status_code)

    assert statuses == [200, 200, 200, 429]
    refused = client.get("/api/v1/me/")
    assert refused.json()["code"] == "throttled"
    assert "Retry-After" in refused


def test_login_free_addresses_are_limited_per_visitor(api_client, db, low_limits):
    statuses = []
    for _ in range(4):
        statuses.append(api_client.get("/api/v1/public/posters/nope.png").status_code)

    assert statuses == [404, 404, 404, 429]


def test_the_health_check_is_never_limited(api_client, db, low_limits):
    for _ in range(10):
        assert api_client.get("/api/v1/health/").status_code == 200
