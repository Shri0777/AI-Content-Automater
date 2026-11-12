"""Walk through the whole app in demo mode, the way a user would.

It registers a new user, saves demo credentials, links a demo social account,
creates a plan, makes a post, saves its poster, approves it and checks it was
published. It only uses the public API, so it tests the real running app,
including the background worker. It needs nothing but Python itself.

    docker compose up -d --build --wait
    docker compose exec web python manage.py create_invite_codes 1
    python3 scripts/demo_walkthrough.py --invite-code <code printed above>

It exits with code 1 if any step fails. Demo posts are canned, not AI output.
"""

import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

# A post is still being made while it has one of these statuses.
WORKING_STATUSES = [
    "researching",
    "drafting",
    "imaging",
    "reviewing",
    "approved",
    "publishing",
]
WAIT_SECONDS = 60
PNG_START = b"\x89PNG"


class WalkthroughFailed(Exception):
    """Raised when the app does not answer the way the walkthrough expects."""


class ApiClient:
    """Sends JSON requests to the API and remembers the access token."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.access_token = None

    def send(self, method, path, body=None):
        """Send one request; return (status code, response bytes)."""
        data = None
        if body is not None:
            data = json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if self.access_token is not None:
            request.add_header("Authorization", f"Bearer {self.access_token}")
        try:
            # The address is checked to start with http:// or https:// in main().
            with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def call(self, method, path, body=None, expected_status=200):
        """Send a request, check the status code and return the JSON answer."""
        status, content = self.send(method, path, body)
        if status != expected_status:
            raise WalkthroughFailed(
                f"{method} {path} answered {status}, expected {expected_status}: "
                f"{content.decode(errors='replace')[:300]}"
            )
        if not content:
            return {}
        return json.loads(content)


def wait_for_api(client):
    """Wait until the health check answers; the server may still be starting."""
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            status, content = client.send("GET", "/api/v1/health/")
        except (urllib.error.URLError, ConnectionError):
            status = 0
        if status == 200:
            return
        time.sleep(1)
    raise WalkthroughFailed(
        f"The API at {client.base_url} did not answer for {WAIT_SECONDS} "
        "seconds. Is it running? (docker compose ps)"
    )


def step(number, text):
    """Print the title of one step."""
    print(f"\n{number}. {text}")


def wait_for_post(client, post_id):
    """Poll a post until it is no longer being worked on; return it."""
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        post = client.call("GET", f"/api/v1/posts/{post_id}/")
        if post["status"] not in WORKING_STATUSES:
            return post
        time.sleep(0.5)
    raise WalkthroughFailed(
        f"Post {post_id} was still working after {WAIT_SECONDS} seconds. "
        "Is the worker running? (docker compose logs worker)"
    )


def sign_up(client, invite_code):
    """Register a new user, log in, and return the email address."""
    email = f"demo-{secrets.token_hex(4)}@example.com"
    password = secrets.token_urlsafe(16)
    step(1, f"Register {email} with the invite code")
    registered = client.call(
        "POST",
        "/api/v1/auth/register/",
        {"email": email, "password": password, "invite_code": invite_code},
        expected_status=201,
    )
    print(f"   Got {len(registered['recovery_codes'])} one-time recovery codes.")
    step(2, "Log in")
    login = client.call(
        "POST", "/api/v1/auth/login/", {"email": email, "password": password}
    )
    client.access_token = login["access"]
    print("   Logged in. The refresh token is in an httpOnly cookie.")
    return email


def set_up_plan(client, preset):
    """Save demo keys, link a demo account, create a plan; return its id."""
    step(3, "Save demo text and image credentials")
    for kind in ["text", "image"]:
        body = {"kind": kind, "adapter": "demo", "api_key": "demo-key-0000"}
        saved = client.call("POST", "/api/v1/credentials/", body, 201)
        print(f"   {kind}: saved, key shown only as ...{saved['key_hint']}")
    step(4, "Link an account on the demo social network")
    account = client.call("POST", "/api/v1/social/link/demo/", None, 201)
    print(f"   Linked '{account['display_name']}'.")
    step(5, f"Create a plan that follows the '{preset}' topic")
    plan_details = {
        "name": "Demo plan",
        "requirements": "Short, friendly posts for developers.",
        "topics": [{"name": "Demo topic", "preset": preset}],
        "account_ids": [account["id"]],
    }
    plan = client.call("POST", "/api/v1/plans/", plan_details, 201)
    print(f"   Plan {plan['id']} created.")
    return plan["id"]


def make_post(client, plan_id, poster_file):
    """Generate a post, show it, save its poster; return the post id."""
    step(6, "Generate a post now (the worker does the work)")
    started = client.call("POST", f"/api/v1/plans/{plan_id}/generate-now/", None, 202)
    post = wait_for_post(client, started["id"])
    if post["status"] != "awaiting_approval":
        raise WalkthroughFailed(f"Post ended as {post['status']}: {post}")
    version = post["versions"][0]
    print(f"   Article:  {post['article']['title']}")
    print(f"   Headline: {version['headline']}")
    print(f"   Verdict:  {version['review']['verdict']}")
    for generation_step in post["steps"]:
        print(f"   - {generation_step['stage']}: {generation_step['duration_ms']} ms")
    step(7, "Download the poster")
    status, png_bytes = client.send("GET", post["poster_url"])
    if status != 200 or not png_bytes.startswith(PNG_START):
        raise WalkthroughFailed(f"The poster did not download (status {status}).")
    with open(poster_file, "wb") as output:
        output.write(png_bytes)
    print(f"   Saved {len(png_bytes)} bytes to {poster_file}")
    return post["id"]


def approve_and_publish(client, post_id):
    """Approve the post and check it was published."""
    step(8, "Approve the post, which publishes it")
    client.call("POST", f"/api/v1/posts/{post_id}/approve/")
    post = wait_for_post(client, post_id)
    if post["status"] != "published":
        raise WalkthroughFailed(f"Post ended as {post['status']}: {post}")
    for publication in post["publications"]:
        print(
            f"   Published to '{publication['account_name']}' "
            f"as {publication['external_id']}"
        )
    step(9, "Check the in-app summary")
    summary = client.call("GET", "/api/v1/me/summary/")
    print(f"   Unread notifications: {summary['unread_notifications']}")


def read_arguments():
    """Read the command-line options."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--invite-code", required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--preset", default="ai_news")
    parser.add_argument("--poster-file", default="demo-poster.png")
    return parser.parse_args()


def main():
    """Run every step and report success or the first failure."""
    options = read_arguments()
    if not options.base_url.startswith(("http://", "https://")):
        sys.exit("--base-url must start with http:// or https://")
    client = ApiClient(options.base_url)
    try:
        wait_for_api(client)
        sign_up(client, options.invite_code)
        plan_id = set_up_plan(client, options.preset)
        post_id = make_post(client, plan_id, options.poster_file)
        approve_and_publish(client, post_id)
    except (WalkthroughFailed, urllib.error.URLError) as error:
        print(f"\nFAILED: {error}")
        sys.exit(1)
    print("\nAll steps passed. Demo content is canned, not real AI output.")


if __name__ == "__main__":
    main()
