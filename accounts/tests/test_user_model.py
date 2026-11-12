"""Tests for the custom User model, which logs in with an email address."""

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_create_user_stores_a_lowercase_email_domain_and_a_hashed_password():
    User = get_user_model()

    user = User.objects.create_user(
        email="Ada@EXAMPLE.com", password="a-long-password-1"
    )

    assert user.email == "Ada@example.com"
    assert user.password != "a-long-password-1"
    assert user.check_password("a-long-password-1")


@pytest.mark.django_db
def test_new_users_start_on_the_free_tier_in_utc():
    User = get_user_model()

    user = User.objects.create_user(
        email="ada@example.com", password="a-long-password-1"
    )

    assert user.tier == "free"
    assert user.timezone == "UTC"
    assert user.is_staff is False


@pytest.mark.django_db
def test_create_user_without_an_email_is_refused():
    User = get_user_model()

    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="a-long-password-1")


@pytest.mark.django_db
def test_create_superuser_can_use_the_admin_site():
    User = get_user_model()

    admin = User.objects.create_superuser(
        email="boss@example.com", password="pw-123-long"
    )

    assert admin.is_staff is True
    assert admin.is_superuser is True


def test_users_log_in_with_their_email_not_a_username():
    User = get_user_model()

    assert User.USERNAME_FIELD == "email"
