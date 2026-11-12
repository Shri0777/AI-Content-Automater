"""Tests for creating an account, which is invite-only by default."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import InviteCode
from accounts.services import create_invite_codes

REGISTER_URL = "/api/v1/auth/register/"
GOOD_PASSWORD = "correct-horse-battery-staple"


def register(api_client, email, invite_code=None):
    """Call the register endpoint and return the response."""
    data = {"email": email, "password": GOOD_PASSWORD}
    if invite_code is not None:
        data["invite_code"] = invite_code
    return api_client.post(REGISTER_URL, data, format="json")


@pytest.mark.django_db
def test_a_valid_invite_code_creates_an_account(api_client):
    code = create_invite_codes(1)[0]

    response = register(api_client, "ada@example.com", code)

    assert response.status_code == 201
    assert response.json()["email"] == "ada@example.com"
    assert "password" not in response.json()
    assert get_user_model().objects.filter(email="ada@example.com").exists()


@pytest.mark.django_db
def test_an_invite_code_works_only_once(api_client):
    code = create_invite_codes(1)[0]
    register(api_client, "ada@example.com", code)

    response = register(api_client, "grace@example.com", code)

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_invite_code"


@pytest.mark.django_db
def test_used_invite_code_remembers_who_used_it(api_client):
    code = create_invite_codes(1)[0]

    register(api_client, "ada@example.com", code)

    invite = InviteCode.objects.get()
    assert invite.used_by.email == "ada@example.com"
    assert invite.used_at is not None


@pytest.mark.django_db
def test_registering_without_an_invite_code_is_refused_in_invite_mode(api_client):
    response = register(api_client, "ada@example.com")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_invite_code"


@pytest.mark.django_db
def test_open_mode_needs_no_invite_code(api_client, settings):
    settings.REGISTRATION_MODE = "open"

    response = register(api_client, "ada@example.com")

    assert response.status_code == 201


@pytest.mark.django_db
def test_closed_mode_refuses_everyone(api_client, settings):
    settings.REGISTRATION_MODE = "closed"
    code = create_invite_codes(1)[0]

    response = register(api_client, "ada@example.com", code)

    assert response.status_code == 403
    assert response.json()["code"] == "registration_closed"


@pytest.mark.django_db
def test_an_email_can_only_have_one_account(api_client, settings):
    settings.REGISTRATION_MODE = "open"
    register(api_client, "ada@example.com")

    response = register(api_client, "ada@example.com")

    assert response.status_code == 400
    assert "email" in response.json()["errors"]


@pytest.mark.django_db
def test_a_weak_password_is_refused(api_client, settings):
    settings.REGISTRATION_MODE = "open"
    data = {"email": "ada@example.com", "password": "123"}

    response = api_client.post(REGISTER_URL, data, format="json")

    assert response.status_code == 400
    assert "password" in response.json()["errors"]
    assert not get_user_model().objects.exists()


@pytest.mark.django_db
def test_failed_registration_does_not_use_up_the_invite_code(api_client):
    code = create_invite_codes(1)[0]
    data = {"email": "ada@example.com", "password": "123", "invite_code": code}
    api_client.post(REGISTER_URL, data, format="json")

    response = register(api_client, "ada@example.com", code)

    assert response.status_code == 201
