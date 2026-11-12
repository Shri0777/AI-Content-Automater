"""Tests for making invite codes, which the operator hands out to new users."""

from io import StringIO

import pytest
from django.core.management import call_command

from accounts.models import InviteCode
from accounts.services import create_invite_codes


@pytest.mark.django_db
def test_invite_codes_are_stored_only_as_hashes():
    codes = create_invite_codes(2)

    for code in codes:
        assert not InviteCode.objects.filter(code_hash=code).exists()
    assert InviteCode.objects.count() == 2


@pytest.mark.django_db
def test_every_invite_code_is_different():
    codes = create_invite_codes(20)

    assert len(set(codes)) == 20


@pytest.mark.django_db
def test_the_command_prints_new_codes_for_the_operator():
    output = StringIO()

    call_command("create_invite_codes", "3", stdout=output)

    printed_lines = output.getvalue().strip().splitlines()
    assert len(printed_lines) == 4
    assert InviteCode.objects.filter(used_by=None).count() == 3
