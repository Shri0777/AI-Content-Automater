"""Encrypt and decrypt secrets such as API keys and social media tokens.

We never store a user's API key as plain text. Before saving, we call
encrypt_text(); when we need the key again, we call decrypt_text().

The work is done by Fernet from the "cryptography" library. This is the only
file that uses that library, so the rest of the code never needs to know
how encryption works. The key comes from the ENCRYPTION_KEY setting.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DecryptionError(Exception):
    """Raised when saved text cannot be decrypted (damaged or wrong key)."""


def get_cipher():
    """Return a Fernet object built from the ENCRYPTION_KEY setting."""
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_text(plain_text):
    """Return an encrypted, safe-to-store version of plain_text."""
    encrypted_bytes = get_cipher().encrypt(plain_text.encode())
    return encrypted_bytes.decode()


def decrypt_text(encrypted_text):
    """Return the original text from encrypted_text."""
    try:
        plain_bytes = get_cipher().decrypt(encrypted_text.encode())
    except InvalidToken:
        # "from None" hides the library's own error, which adds nothing here.
        raise DecryptionError(
            "Saved secret could not be decrypted. "
            "It may be damaged or encrypted with a different key."
        ) from None
    return plain_bytes.decode()
