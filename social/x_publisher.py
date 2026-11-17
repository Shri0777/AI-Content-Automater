"""Link X (formerly Twitter) accounts and post to them with the X API v2.

Linking uses OAuth 2.0 with PKCE. Access tokens last two hours; the
offline.access scope adds a refresh token, which works only once (every
refresh returns a new one). Our app is a "confidential client", so token
requests send the app's id and secret in a Basic Authorization header.

Docs (checked 2026-11-17):
- https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code
- https://docs.x.com/x-api/media/upload-media (one-request image upload)
- https://docs.x.com/x-api/posts/create-post
"""

import base64
from urllib.parse import quote, urlencode

from django.conf import settings

from core import web
from social.publishers import (
    Publisher,
    access_token_of,
    bearer,
    read_answer,
    refresh_token_of,
)

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
SCOPES = "tweet.read tweet.write users.read media.write offline.access"


def api_url(path):
    """Return the full address of an X API path."""
    return settings.SOCIAL_API_URLS["x"] + path


def app_auth_header():
    """Return the Basic Authorization header made from our app's id and secret."""
    app = settings.SOCIAL_APPS["x"]
    pair = f"{app['client_id']}:{app['client_secret']}"
    return {"Authorization": "Basic " + base64.b64encode(pair.encode()).decode()}


def ask_for_tokens(form):
    """Send a token request and return the new tokens."""
    answer = web.post_form(api_url("/2/oauth2/token"), app_auth_header(), form)
    return {
        "access_token": read_answer(answer, ["access_token"], "X"),
        "refresh_token": answer.get("refresh_token"),
        "expires_in": answer.get("expires_in"),
        "scopes": answer.get("scope", ""),
    }


class XPublisher(Publisher):
    """Posts a caption with the poster image to an X account."""

    uses_oauth = True

    def authorization_url(self, state, code_challenge, redirect_uri):
        """Return X's approval page for this link attempt."""
        params = {
            "response_type": "code",
            "client_id": settings.SOCIAL_APPS["x"]["client_id"],
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        # X's examples write spaces as %20, which quote() does.
        return f"{AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"

    def finish_link(self, code, code_verifier, redirect_uri):
        """Swap the approval code for tokens and find the user's X account."""
        tokens = ask_for_tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )
        me_url = api_url("/2/users/me?user.fields=username")
        answer = web.get_json(me_url, bearer(tokens["access_token"]))
        tokens["external_id"] = read_answer(answer, ["data", "id"], "X")
        username = read_answer(answer, ["data", "username"], "X")
        tokens["display_name"] = f"@{username}"
        tokens["network"] = "x"
        return [tokens]

    def publish(self, account, content):
        """Upload the poster, then post the caption with it."""
        headers = bearer(access_token_of(account))
        upload = web.post_files(
            api_url("/2/media/upload"),
            headers,
            {"media_category": "tweet_image"},
            {"media": ("poster.png", content.image_bytes, "image/png")},
        )
        media_id = read_answer(upload, ["data", "id"], "X")
        body = {"text": content.caption, "media": {"media_ids": [media_id]}}
        answer = web.post_json(api_url("/2/tweets"), headers, body)
        return read_answer(answer, ["data", "id"], "X")

    def refresh_tokens(self, account):
        """Swap the refresh token (usable once) for new tokens."""
        refresh_token = refresh_token_of(account)
        if not refresh_token:
            return None
        form = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        return ask_for_tokens(form)

    def revoke(self, account):
        """Cancel the link at X. Revoking the refresh token ends the whole grant."""
        token = refresh_token_of(account) or access_token_of(account)
        web.post_form(api_url("/2/oauth2/revoke"), app_auth_header(), {"token": token})
