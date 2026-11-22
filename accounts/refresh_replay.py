"""Give the same answer to a refresh token that was swapped a moment ago.

Each refresh swaps the refresh cookie for a new one and cancels the old one.
If the reply carrying the new cookie never reaches the browser (the page was
reloaded mid-request), or two tabs refresh at once, the old cookie arrives
again. Refusing it would log the user out, so for a few seconds the same new
tokens are returned instead. Logging out still wins: once the new refresh
token is cancelled, the old one is refused too.

The cache key is a hash of the old token; the new tokens sit in the cache
(Redis) for at most REFRESH_REPLAY_SECONDS.
"""

import hashlib

from django.core.cache import cache
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

REFRESH_REPLAY_SECONDS = 30


def remember(refresh_token, tokens):
    """Keep the tokens an old refresh token was swapped for, for a few seconds."""
    cache.set(replay_key(refresh_token), tokens, REFRESH_REPLAY_SECONDS)


def replay_key(refresh_token):
    """Return the cache key for a swapped token (a hash, never the token)."""
    return "refresh-replay:" + hashlib.sha256(refresh_token.encode()).hexdigest()


def recall(refresh_token):
    """Return the tokens a just-swapped refresh token was exchanged for.

    Return None if there are none: the swap was too long ago, never
    happened, or the new refresh token has since been cancelled (logout).
    """
    tokens = cache.get(replay_key(refresh_token))
    if tokens is None or is_cancelled(tokens["refresh"]):
        return None
    return tokens


def is_cancelled(refresh_token):
    """Return True if a refresh token was logged out, swapped or has expired."""
    try:
        RefreshToken(refresh_token)
    except TokenError:
        return True
    return False
