"""Routes that make the stub server answer like each social platform.

The answer shapes follow each platform's API reference (links are in the
publisher files in social/). Token requests hand out numbered tokens, so a
test can tell a refreshed token from the first one.
"""

BUFFER_PATH = "/buffer"
X_TOKEN_PATH = "/x/2/oauth2/token"
X_REVOKE_PATH = "/x/2/oauth2/revoke"
X_ME_PATH = "/x/2/users/me"
X_UPLOAD_PATH = "/x/2/media/upload"
X_TWEETS_PATH = "/x/2/tweets"
LINKEDIN_TOKEN_PATH = "/linkedin-oauth/accessToken"
LINKEDIN_USERINFO_PATH = "/linkedin/v2/userinfo"
LINKEDIN_IMAGES_PATH = "/linkedin/rest/images"
LINKEDIN_UPLOAD_PATH = "/linkedin-upload/image-1"
LINKEDIN_POSTS_PATH = "/linkedin/rest/posts"
LINKEDIN_DOCUMENTS_PATH = "/linkedin/rest/documents"
LINKEDIN_DOCUMENT_UPLOAD_PATH = "/linkedin-upload/document-1"
FACEBOOK_TOKEN_PATH = "/facebook/oauth/access_token"
FACEBOOK_PAGES_PATH = "/facebook/me/accounts"
FACEBOOK_PHOTOS_PATH = "/facebook/page-1/photos"


def point_settings_at(settings, stub_server):
    """Make every platform's API address lead to the stub server."""
    base = stub_server.base_url
    settings.SOCIAL_API_URLS = {
        "buffer": base + BUFFER_PATH,
        "x": base + "/x",
        "linkedin": base + "/linkedin",
        "linkedin_oauth": base + "/linkedin-oauth",
        "facebook": base + "/facebook",
    }
    settings.SOCIAL_APPS = {
        "x": {"client_id": "x-app", "client_secret": "x-app-secret"},
        "linkedin": {"client_id": "li-app", "client_secret": "li-app-secret"},
        "facebook": {"client_id": "fb-app", "client_secret": "fb-app-secret"},
    }
    settings.PUBLIC_API_URL = "http://127.0.0.1:8000"
    settings.FRONTEND_URL = "http://localhost:5173"


class TokenCounter:
    """Hands out access-1, access-2, ... like a platform's token endpoint."""

    def __init__(self, expires_in, with_refresh_token):
        self.number = 0
        self.expires_in = expires_in
        self.with_refresh_token = with_refresh_token

    def answer(self, form):
        """Return a token answer with the next numbered tokens."""
        self.number = self.number + 1
        tokens = {
            "token_type": "bearer",
            "access_token": f"access-{self.number}",
            "expires_in": self.expires_in,
            "scope": "granted-scopes",
        }
        if self.with_refresh_token:
            tokens["refresh_token"] = f"refresh-{self.number}"
        return {"json": tokens}


def add_x_routes(stub_server):
    """Answer like X: tokens last two hours and come with a refresh token."""
    counter = TokenCounter(expires_in=7200, with_refresh_token=True)
    stub_server.set_route("POST", X_TOKEN_PATH, counter.answer)
    stub_server.set_route("POST", X_REVOKE_PATH, {"json": {"revoked": True}})
    me = {"data": {"id": "2244994945", "name": "Ada", "username": "ada_dev"}}
    stub_server.set_route("GET", X_ME_PATH, {"json": me})
    upload = {"data": {"id": "1880028106020515840", "media_key": "3_1880"}}
    stub_server.set_route("POST", X_UPLOAD_PATH, {"json": upload})
    tweet = {"data": {"id": "1445880548472328192", "text": "posted"}}
    stub_server.set_route("POST", X_TWEETS_PATH, {"status": 201, "json": tweet})
    return counter


def add_linkedin_document_routes(stub_server):
    """Answer LinkedIn's document upload (the slides of a post, as a PDF)."""
    document_upload = {
        "value": {
            "uploadUrlExpiresAt": 1650567510704,
            "uploadUrl": stub_server.base_url + LINKEDIN_DOCUMENT_UPLOAD_PATH,
            "document": "urn:li:document:D5510AQFx87994pYx0Q",
        }
    }
    stub_server.set_route("POST", LINKEDIN_DOCUMENTS_PATH, {"json": document_upload})
    empty = {"status": 201, "body": b""}
    stub_server.set_route("PUT", LINKEDIN_DOCUMENT_UPLOAD_PATH, empty)


def add_linkedin_routes(stub_server):
    """Answer like LinkedIn: 60-day tokens with no refresh token."""
    counter = TokenCounter(expires_in=5184000, with_refresh_token=False)
    stub_server.set_route("POST", LINKEDIN_TOKEN_PATH, counter.answer)
    userinfo = {"sub": "782bbtaQ", "name": "Ada Lovelace"}
    stub_server.set_route("GET", LINKEDIN_USERINFO_PATH, {"json": userinfo})
    upload = {
        "value": {
            "uploadUrlExpiresAt": 1650567510704,
            "uploadUrl": stub_server.base_url + LINKEDIN_UPLOAD_PATH,
            "image": "urn:li:image:C4E10AQFoyyAjHPMQuQ",
        }
    }
    stub_server.set_route("POST", LINKEDIN_IMAGES_PATH, {"json": upload})
    stub_server.set_route("PUT", LINKEDIN_UPLOAD_PATH, {"status": 201, "body": b""})
    add_linkedin_document_routes(stub_server)
    created = {
        "status": 201,
        "body": b"",
        "headers": {"x-restli-id": "urn:li:share:6844785523593134080"},
    }
    stub_server.set_route("POST", LINKEDIN_POSTS_PATH, created)
    return counter


def add_facebook_routes(stub_server, pages):
    """Answer like Meta's Graph API, with the given Pages from /me/accounts."""
    counter = TokenCounter(expires_in=5183944, with_refresh_token=False)
    stub_server.set_route("GET", FACEBOOK_TOKEN_PATH, counter.answer)
    stub_server.set_route("GET", FACEBOOK_PAGES_PATH, {"json": {"data": pages}})
    photo = {"id": "1234567890", "post_id": "page-1_9876543210"}
    stub_server.set_route("POST", FACEBOOK_PHOTOS_PATH, {"json": photo})


def facebook_page(page_id, tasks):
    """Return one Page as /me/accounts lists it."""
    return {
        "id": page_id,
        "name": f"Page {page_id}",
        "category": "Software",
        "access_token": f"page-token-{page_id}",
        "tasks": tasks,
    }


def buffer_answer(body):
    """Answer a Buffer GraphQL request based on which query it sends."""
    query = body["query"]
    if "organizations" in query:
        organizations = [
            {"id": "org-1", "name": "Mine"},
            {"id": "org-2", "name": "Team"},
        ]
        return {"json": {"data": {"account": {"organizations": organizations}}}}
    if "channels" in query:
        organization = body["variables"]["organizationId"]
        channel = {
            "id": f"channel-{organization}",
            "name": f"Ada {organization}",
            "service": "linkedin",
        }
        return {"json": {"data": {"channels": [channel]}}}
    post = {"post": {"id": "buffer-post-1"}}
    return {"json": {"data": {"createPost": post}}}


def add_buffer_routes(stub_server):
    """Answer like Buffer's GraphQL API."""
    stub_server.set_route("POST", BUFFER_PATH, buffer_answer)
