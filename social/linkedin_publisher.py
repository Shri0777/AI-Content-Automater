"""Link LinkedIn members and post to their profile with LinkedIn's REST API.

This uses LinkedIn's self-serve products "Share on LinkedIn" (scope
w_member_social) and "Sign In with LinkedIn using OpenID Connect" (scopes
openid and profile). Access tokens last 60 days. LinkedIn gives refresh
tokens only to approved partners, so for most apps the user must link the
account again before it expires; social/tokens.py warns them a week ahead.

A post's slides go out as one document post: a PDF that LinkedIn shows as
pages people swipe through. Posting takes three calls: ask LinkedIn for an
upload address, upload the PDF there, then create the post with the
document's id and a title. Posts made before slides have no PDF and are
posted the same way with their image instead. Documents can be up to 100 MB
and 300 pages; w_member_social is enough for a member's own posts.

Docs (checked 2026-11-17; documents-api checked 2026-11-22), on
learn.microsoft.com/en-us/linkedin:
- shared/authentication/authorization-code-flow
- marketing/community-management/shares/images-api
- marketing/community-management/shares/documents-api
- marketing/community-management/shares/posts-api

Not yet confirmed against the live API (see plan.md §10): that the "sub"
from /v2/userinfo is the id used in urn:li:person:<id>.
"""

from urllib.parse import urlencode

from django.conf import settings

from core import web
from core.errors import ProviderError
from social.publishers import (
    Publisher,
    access_token_of,
    bearer,
    read_answer,
    refresh_token_of,
)

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
SCOPES = "openid profile w_member_social"


def api_url(path):
    """Return the full address of a LinkedIn API path."""
    return settings.SOCIAL_API_URLS["linkedin"] + path


def rest_headers(token):
    """Return the headers every LinkedIn /rest/ request needs."""
    headers = bearer(token)
    headers["LinkedIn-Version"] = settings.LINKEDIN_API_VERSION
    headers["X-Restli-Protocol-Version"] = "2.0.0"
    return headers


def ask_for_tokens(app, form):
    """Send a token request (with the app's id and secret) and return tokens."""
    form["client_id"] = app["client_id"]
    form["client_secret"] = app["client_secret"]
    url = settings.SOCIAL_API_URLS["linkedin_oauth"] + "/accessToken"
    answer = web.post_form(url, {}, form)
    return {
        "access_token": read_answer(answer, ["access_token"], "LinkedIn"),
        "refresh_token": answer.get("refresh_token"),
        "expires_in": answer.get("expires_in"),
        "scopes": answer.get("scope", ""),
    }


class LinkedInPublisher(Publisher):
    """Posts a caption with the poster image to a member's LinkedIn profile."""

    uses_oauth = True

    def authorization_url(self, state, code_challenge, redirect_uri):
        """Return LinkedIn's approval page. LinkedIn's web flow has no PKCE."""
        params = {
            "response_type": "code",
            "client_id": self.app["client_id"],
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": SCOPES,
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def finish_link(self, code, code_verifier, redirect_uri):
        """Swap the approval code for tokens and find the member's id and name."""
        tokens = ask_for_tokens(
            self.app,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        answer = web.get_json(api_url("/v2/userinfo"), bearer(tokens["access_token"]))
        tokens["external_id"] = read_answer(answer, ["sub"], "LinkedIn")
        tokens["display_name"] = answer.get("name", "LinkedIn member")
        tokens["network"] = "linkedin"
        return [tokens]

    def upload(self, account, kind, data):
        """Upload an image or a document; return its id (urn:li:image:...).

        kind is "image" or "document": the two upload the same way.
        """
        token = access_token_of(account)
        body = {
            "initializeUploadRequest": {"owner": f"urn:li:person:{account.external_id}"}
        }
        url = api_url(f"/rest/{kind}s?action=initializeUpload")
        answer = web.post_json(url, rest_headers(token), body)
        upload_url = read_answer(answer, ["value", "uploadUrl"], "LinkedIn")
        web.put_bytes(upload_url, bearer(token), data)
        return read_answer(answer, ["value", kind], "LinkedIn")

    def media_for(self, account, content):
        """Upload the slides as a document (or else the poster image)."""
        if content.document_bytes:
            document_id = self.upload(account, "document", content.document_bytes)
            return {"id": document_id, "title": content.document_title}
        return {"id": self.upload(account, "image", content.image_bytes)}

    def publish(self, account, content):
        """Upload the slides or poster, create the post, return the post's id."""
        media = self.media_for(account, content)
        body = {
            "author": f"urn:li:person:{account.external_id}",
            "commentary": content.caption,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {"media": media},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        headers = rest_headers(access_token_of(account))
        answer = web.send("POST", api_url("/rest/posts"), headers, {"json": body})
        # LinkedIn returns the new post's id in a header, not in the body.
        post_id = answer.headers.get("x-restli-id", "")
        if post_id == "":
            raise ProviderError("LinkedIn did not say which post it created.")
        return post_id

    def refresh_tokens(self, account):
        """Refresh the token, which only works for LinkedIn-approved partners."""
        refresh_token = refresh_token_of(account)
        if not refresh_token:
            return None
        return ask_for_tokens(
            self.app, {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
