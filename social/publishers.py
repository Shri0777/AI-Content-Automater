"""The base class for linking accounts and sending posts to a platform.

This is the adapter pattern: Publisher is the base class, and every platform
has one subclass that knows how to talk to it (for example x_publisher.py,
and demo/publisher.py for the fake demo network). The rest of the code calls
social.platforms.get_publisher(platform), so it never needs to know which
platform it is talking to.

Data passed between the publishers and the rest of the code is plain dicts:

- A found account (from finish_link or Buffer's find_channels):
  {"external_id", "display_name", "network", "access_token",
   "refresh_token", "expires_in", "scopes"}
- New tokens (from refresh_tokens):
  {"access_token", "refresh_token", "expires_in", "scopes"}

expires_in is seconds from now, or None when the token does not expire.
refresh_token is left out (or None) when the platform gives none.
"""

from core.crypto import decrypt_text
from core.errors import ProviderError


def bearer(token):
    """Return the Authorization header that sends token."""
    return {"Authorization": f"Bearer {token}"}


def read_answer(answer, keys, platform_name):
    """Return answer[keys[0]][keys[1]]...; raise ProviderError if it is missing.

    A platform that changes its answer's shape then gives a clear error
    instead of a crash.
    """
    value = answer
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ProviderError(
                f"{platform_name} answered in an unexpected way "
                f"(no '{'.'.join(keys)}')."
            )
        value = value[key]
    return value


class PostContent:
    """What gets published: the caption and the poster image.

    Some platforms take the image bytes; others (Buffer) download it from
    image_url themselves.
    """

    def __init__(self, caption, image_bytes, image_url):
        self.caption = caption
        self.image_bytes = image_bytes
        self.image_url = image_url


def access_token_of(account):
    """Return the account's access token as plain text."""
    return decrypt_text(account.encrypted_token)


def refresh_token_of(account):
    """Return the account's refresh token as plain text, or None if none."""
    if not account.encrypted_refresh_token:
        return None
    return decrypt_text(account.encrypted_refresh_token)


class Publisher:
    """The base class every platform's publisher follows."""

    # True for platforms linked by sending the user to the platform's own
    # approval page (OAuth). Buffer and the demo network work differently.
    uses_oauth = False

    def authorization_url(self, state, code_challenge, redirect_uri):
        """Return the platform page where the user approves the link."""
        raise NotImplementedError("This platform is not linked through OAuth.")

    def finish_link(self, code, code_verifier, redirect_uri):
        """Swap the approval code for tokens; return a list of found accounts."""
        raise NotImplementedError("This platform is not linked through OAuth.")

    def publish(self, account, content):
        """Post content (a PostContent) to account; return the platform's post id.

        Raise core.errors.ProviderError if the platform refuses or fails.
        """
        raise NotImplementedError("Each publisher must define publish().")

    def refresh_tokens(self, account):
        """Return new tokens for account, or None if this platform cannot."""
        return None

    def revoke(self, account):
        """Tell the platform to cancel the account's tokens, where it can.

        Platforms without a revoke call keep the default, which does nothing;
        the tokens are still deleted from our database.
        """
