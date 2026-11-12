"""Tests for encrypt_text and decrypt_text, which protect saved API keys."""

import pytest
from cryptography.fernet import Fernet

from core.crypto import DecryptionError, decrypt_text, encrypt_text


def test_decrypting_gives_back_the_original_text():
    secret = encrypt_text("sk-my-api-key")

    assert decrypt_text(secret) == "sk-my-api-key"


def test_encrypted_text_does_not_contain_the_original():
    secret = encrypt_text("sk-my-api-key")

    assert "sk-my-api-key" not in secret


def test_encrypting_the_same_text_twice_gives_different_results():
    first = encrypt_text("sk-my-api-key")
    second = encrypt_text("sk-my-api-key")

    assert first != second


def test_changed_encrypted_text_is_refused():
    secret = encrypt_text("sk-my-api-key")
    damaged = secret[:-4] + "AAAA"

    with pytest.raises(DecryptionError):
        decrypt_text(damaged)


def test_text_encrypted_with_another_key_is_refused(settings):
    secret = encrypt_text("sk-my-api-key")
    settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

    with pytest.raises(DecryptionError):
        decrypt_text(secret)
