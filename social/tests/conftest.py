"""Shared setup for the social tests: users, and platforms on a stub server."""

import pytest
from django.contrib.auth import get_user_model

from tests.social_stubs import point_settings_at


def make_user(email):
    """Create and return a saved user."""
    return get_user_model().objects.create_user(
        email=email, password="correct-horse-battery-staple"
    )


@pytest.fixture
def user(db):
    """The logged-in user in these tests."""
    return make_user("ada@example.com")


@pytest.fixture
def other_user(db):
    """A second user, to check that users never see each other's accounts."""
    return make_user("grace@example.com")


@pytest.fixture
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def platforms(stub_server, settings):
    """The stub server, with every platform's address pointing at it."""
    point_settings_at(settings, stub_server)
    return stub_server
