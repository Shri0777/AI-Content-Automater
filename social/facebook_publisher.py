"""Link Facebook Pages and post photos to them with Meta's Graph API.

The user approves our app with Facebook Login, then we swap their short-lived
token for a long-lived one and ask which Pages they manage. Each Page has its
own Page token; Meta's docs say Page tokens made from a long-lived user token
have no expiry date (they stop working only in special cases, such as a
password change). So there is nothing to refresh: a refused token marks the
account "needs_reauth" when the next post is sent.

Instagram is not linked here yet: Meta downloads Instagram images from a
public address and needs JPEG files (see plan.md, Phase 4 notes).

Docs (checked 2026-11-17), on developers.facebook.com/docs:
- facebook-login/guides/advanced/manual-flow
- facebook-login/guides/access-tokens/get-long-lived
- graph-api/reference/page/photos
"""

from urllib.parse import urlencode

from django.conf import settings

from core import web
from core.errors import ProviderError
from social.publishers import Publisher, access_token_of, read_answer

DIALOG_URL = "https://www.facebook.com/v27.0/dialog/oauth"
SCOPES = "pages_show_list,pages_manage_posts,pages_read_engagement"


def graph_url(path, params):
    """Return the full address of a Graph API path with its query values."""
    return f"{settings.SOCIAL_API_URLS['facebook']}{path}?{urlencode(params)}"


def get_user_token(code, redirect_uri):
    """Swap the approval code for a long-lived user token."""
    app = settings.SOCIAL_APPS["facebook"]
    app_params = {"client_id": app["client_id"], "client_secret": app["client_secret"]}
    params = {"redirect_uri": redirect_uri, "code": code}
    params.update(app_params)
    answer = web.get_json(graph_url("/oauth/access_token", params), {})
    short_token = read_answer(answer, ["access_token"], "Facebook")
    params = {"grant_type": "fb_exchange_token", "fb_exchange_token": short_token}
    params.update(app_params)
    answer = web.get_json(graph_url("/oauth/access_token", params), {})
    return read_answer(answer, ["access_token"], "Facebook")


def page_to_account(page):
    """Turn one Page from /me/accounts into a found account."""
    return {
        "external_id": read_answer(page, ["id"], "Facebook"),
        "display_name": page.get("name", "Facebook Page"),
        "network": "facebook",
        "access_token": read_answer(page, ["access_token"], "Facebook"),
        "expires_in": None,
        "scopes": SCOPES,
    }


class FacebookPublisher(Publisher):
    """Posts the poster with its caption to a Facebook Page."""

    uses_oauth = True

    def authorization_url(self, state, code_challenge, redirect_uri):
        """Return Facebook's approval page. Facebook Login has no PKCE here."""
        params = {
            "client_id": settings.SOCIAL_APPS["facebook"]["client_id"],
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": SCOPES,
            "response_type": "code",
        }
        return f"{DIALOG_URL}?{urlencode(params)}"

    def finish_link(self, code, code_verifier, redirect_uri):
        """Return every Page the user manages where they may create posts."""
        user_token = get_user_token(code, redirect_uri)
        url = graph_url("/me/accounts", {"access_token": user_token})
        pages = read_answer(web.get_json(url, {}), ["data"], "Facebook")
        accounts = []
        for page in pages:
            if "CREATE_CONTENT" in page.get("tasks", []):
                accounts.append(page_to_account(page))
        if not accounts:
            raise ProviderError(
                "None of your Facebook Pages let you create posts through this app."
            )
        return accounts

    def publish(self, account, content):
        """Upload the poster as a Page photo with the caption; return the post id."""
        url = f"{settings.SOCIAL_API_URLS['facebook']}/{account.external_id}/photos"
        form = {"caption": content.caption, "access_token": access_token_of(account)}
        files = {"source": ("poster.png", content.image_bytes, "image/png")}
        answer = web.post_files(url, {}, form, files)
        return answer.get("post_id") or read_answer(answer, ["id"], "Facebook")
