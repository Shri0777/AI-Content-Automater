"""Tests for recovery codes: the way back in when a password is forgotten.

There is no email (ADR-012), so each user gets one-time recovery codes when
they register. Each code can reset the password once.
"""

import string

import pytest
from django.contrib.auth import get_user_model

from accounts.models import RecoveryCode
from accounts.services import create_recovery_codes, make_recovery_code

RECOVER_URL = "/api/v1/auth/recover/"
NEW_CODES_URL = "/api/v1/auth/recovery-codes/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
OLD_PASSWORD = "correct-horse-battery-staple"
NEW_PASSWORD = "a-brand-new-long-password"


@pytest.fixture
def user(db):
    """A saved user."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password=OLD_PASSWORD
    )


def recover(api_client, code, email="ada@example.com", password=NEW_PASSWORD):
    """Call the recover endpoint and return the response."""
    data = {"email": email, "recovery_code": code, "new_password": password}
    return api_client.post(RECOVER_URL, data, format="json")


def strip_separators(code):
    """Return the code without spaces or dashes, the way it is checked."""
    return code.replace("-", "").replace(" ", "")


# --- make_recovery_code(): one new code ---


def test_a_recovery_code_is_text_made_of_letters_digits_and_separators():
    allowed = set(string.ascii_letters + string.digits + "- ")

    code = make_recovery_code()

    assert isinstance(code, str)
    assert set(code) <= allowed


def test_a_recovery_code_is_long_enough_to_be_hard_to_guess():
    code = make_recovery_code()

    assert len(strip_separators(code)) >= 10


def test_recovery_codes_do_not_repeat():
    codes = set()
    for _ in range(1000):
        codes.add(make_recovery_code())

    assert len(codes) == 1000


# --- Getting codes ---


@pytest.mark.django_db
def test_registration_returns_eight_different_recovery_codes(api_client, settings):
    settings.REGISTRATION_MODE = "open"
    data = {"email": "ada@example.com", "password": OLD_PASSWORD}

    response = api_client.post("/api/v1/auth/register/", data, format="json")

    codes = response.json()["recovery_codes"]
    assert len(codes) == 8
    assert len(set(codes)) == 8


def test_codes_are_stored_only_as_slow_hashes(user):
    codes = create_recovery_codes(user)

    for saved in RecoveryCode.objects.filter(user=user):
        assert saved.code_hash not in codes
        assert saved.code_hash.startswith(("pbkdf2", "md5", "argon2"))


# --- Using a code ---


def test_a_valid_code_resets_the_password(api_client, user):
    code = create_recovery_codes(user)[0]

    response = recover(api_client, code)

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert response.json()["recovery_codes_left"] == 7


def test_a_code_works_only_once(api_client, user):
    code = create_recovery_codes(user)[0]
    recover(api_client, code)

    response = recover(api_client, code, password="yet-another-long-password")

    assert response.status_code == 400
    assert response.json()["code"] == "recovery_failed"


def test_codes_are_accepted_in_any_case_and_with_extra_spaces(api_client, user):
    code = create_recovery_codes(user)[0]
    typed_loosely = " " + code.lower() + " "

    response = recover(api_client, typed_loosely)

    assert response.status_code == 200


def test_a_wrong_code_and_an_unknown_email_get_the_same_answer(api_client, user):
    create_recovery_codes(user)

    wrong_code = recover(api_client, "NOT-A-REAL-CODE")
    unknown_email = recover(api_client, "NOT-A-REAL-CODE", email="nobody@example.com")

    assert wrong_code.status_code == unknown_email.status_code == 400
    assert wrong_code.json() == unknown_email.json()


def test_a_weak_new_password_is_refused_and_the_code_is_kept(api_client, user):
    code = create_recovery_codes(user)[0]

    response = recover(api_client, code, password="123")

    assert response.status_code == 400
    assert recover(api_client, code).status_code == 200


def test_recovering_logs_the_user_out_everywhere(api_client, user):
    login = {"email": "ada@example.com", "password": OLD_PASSWORD}
    api_client.post(LOGIN_URL, login, format="json")
    code = create_recovery_codes(user)[0]

    recover(api_client, code)

    response = api_client.post(REFRESH_URL, HTTP_X_REQUESTED_BY="test-suite")
    assert response.status_code == 401


# --- Making a new set ---


def test_new_codes_need_a_login(api_client, db):
    assert api_client.post(NEW_CODES_URL).status_code == 401


def test_a_new_set_replaces_the_old_codes(api_client, user):
    old_code = create_recovery_codes(user)[0]
    api_client.force_authenticate(user)

    response = api_client.post(NEW_CODES_URL, {"password": OLD_PASSWORD})

    assert response.status_code == 201
    assert len(response.json()["recovery_codes"]) == 8
    api_client.force_authenticate(None)
    assert recover(api_client, old_code).status_code == 400


def test_new_codes_need_the_password_again(api_client, user):
    old_code = create_recovery_codes(user)[0]
    api_client.force_authenticate(user)

    wrong = api_client.post(NEW_CODES_URL, {"password": "not-my-password"})
    missing = api_client.post(NEW_CODES_URL, {})

    assert wrong.status_code == 403
    assert wrong.json()["code"] == "wrong_password"
    assert missing.status_code == 400
    # A stolen login token alone cannot replace the codes: the old one works.
    assert recover(api_client, old_code).status_code == 200
