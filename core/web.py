"""Talk to outside services over HTTP, safely. The only file that uses httpx.

Users can type their own provider address (base_url), so every request is
checked first. These rules protect our own network (SSRF):
- only https (http too when ALLOW_PRIVATE_PROVIDER_URLS is on)
- the host must resolve to public IP addresses only
- redirects are never followed
- answers larger than MAX_RESPONSE_BYTES are refused

Failures become one of three errors from core/errors.py, so callers know
what to do: ProviderBusy (try later), ProviderKeyRejected (fix the key) or
ProviderError (give up).

Every connection is made through core/safe_network.py, which checks the
address again at the moment of connecting and connects to exactly that
address, so a DNS server cannot switch it to a private one in between
("DNS rebinding").
"""

import json
from urllib.parse import parse_qsl, urlsplit

import httpx
from django.conf import settings

from core.errors import (
    ProviderBusy,
    ProviderError,
    ProviderKeyRejected,
    ProviderNoAnswer,
)
from core.safe_network import UnsafeAddress, checked_transport, public_address_of

TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
KEY_REJECTED_STATUSES = [401, 403]
TRY_LATER_STATUSES = [408, 409, 425, 429, 500, 502, 503, 504]
MAX_ERROR_TEXT = 300


class Redirected(ProviderError):
    """Raised when a service answers "look elsewhere"; location is where.

    Redirects are never followed automatically. A caller that wants to
    follow one sends a new request to location, which is checked again.
    """

    def __init__(self, message, location):
        super().__init__(message)
        self.location = location


def check_url_format(url):
    """Return the host of url, or raise UnsafeAddress if its form is not allowed.

    This only looks at the text, so it is quick enough to run when a user
    saves a credential.
    """
    allowed_schemes = ["https"]
    if settings.ALLOW_PRIVATE_PROVIDER_URLS:
        allowed_schemes = ["https", "http"]
    parts = urlsplit(url)
    if parts.scheme not in allowed_schemes or not parts.hostname:
        raise UnsafeAddress(f"Use an address that starts with {allowed_schemes[0]}://")
    if parts.username or parts.password:
        raise UnsafeAddress("The address must not contain a user name or password.")
    return parts.hostname


def check_address(url):
    """Raise UnsafeAddress unless every IP address of url's host is public.

    Requests check this again when they connect (core/safe_network.py);
    checking first gives a clear error before any work is done.
    """
    host = check_url_format(url)
    if settings.ALLOW_PRIVATE_PROVIDER_URLS:
        return
    public_address_of(host)


class Answer:
    """The parts of a response the rest of the code needs."""

    def __init__(self, status, headers, content):
        self.status = status
        self.headers = headers
        self.content = content


def find_secrets(url, headers, payload):
    """Return every header, form and address value that could be a secret.

    Some platforms (Facebook's token exchange) take secrets in the address.
    """
    secrets = []
    for value in headers.values():
        secrets.append(value.split(" ")[-1])
    for value in payload.get("form", {}).values():
        secrets.append(str(value))
    for _name, value in parse_qsl(urlsplit(url).query):
        secrets.append(value)
    return secrets


def hide_secrets(text, secrets):
    """Return text with each secret (8 characters or longer) replaced."""
    for secret in secrets:
        if len(secret) >= 8:
            text = text.replace(secret, "[hidden]")
    return text


def read_limited(response):
    """Return the response body, refusing one larger than MAX_RESPONSE_BYTES."""
    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ProviderError("The service sent back far more data than expected.")
    return bytes(content)


def check_status(status, content, url, secrets, location):
    """Raise the right error for a status code that is not a success.

    304 ("not modified") counts as a success: it only comes back when we
    asked for a feed "only if it changed".
    """
    if status < 300 or status == 304:
        return
    host = urlsplit(url).hostname
    if status in KEY_REJECTED_STATUSES:
        raise ProviderKeyRejected(
            f"{host} refused the API key (HTTP {status}). "
            "Check the key and what it is allowed to do."
        )
    if status in TRY_LATER_STATUSES:
        raise ProviderBusy(f"{host} is busy or having problems (HTTP {status}).")
    if status < 400:
        raise Redirected(
            f"{host} tried to redirect us, which is not allowed.", location
        )
    detail = content.decode(errors="replace")[:MAX_ERROR_TEXT]
    raise ProviderError(
        f"{host} refused the request (HTTP {status}): {hide_secrets(detail, secrets)}"
    )


def exchange(method, url, headers, payload):
    """Send the request over the network and return (response, body bytes)."""
    with httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=False,
        trust_env=False,
        transport=checked_transport(),
    ) as client:
        with client.stream(
            method,
            url,
            headers=headers,
            json=payload.get("json"),
            data=payload.get("form"),
            files=payload.get("files"),
            content=payload.get("raw"),
        ) as response:
            return response, read_limited(response)


def send(method, url, headers, payload=None):
    """Send one request and return an Answer.

    payload is a dict that says what goes in the body, using these keys:
    "json" (a dict sent as JSON), "form" (a dict sent as a web form),
    "files" (a file upload, together with "form" for the other fields) or
    "raw" (bytes sent as they are). Leave it out to send no body.
    """
    if payload is None:
        payload = {}
    check_address(url)
    try:
        response, content = exchange(method, url, headers, payload)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # Nothing was sent: the connection itself failed.
        raise ProviderBusy("The service could not be reached.") from None
    except (httpx.TimeoutException, httpx.TransportError):
        # The request went out, but the answer never came back.
        raise ProviderNoAnswer(
            "The service did not answer in time; it may still have acted."
        ) from None
    secrets = find_secrets(url, headers, payload)
    location = response.headers.get("location", "")
    check_status(response.status_code, content, url, secrets, location)
    return Answer(response.status_code, response.headers, content)


def parse_json(content):
    """Return the JSON in content, or raise ProviderError if it is not JSON."""
    try:
        return json.loads(content)
    except ValueError:
        raise ProviderError(
            "The service answered with something that is not JSON."
        ) from None


def post_json(url, headers, body):
    """POST body as JSON and return the JSON answer."""
    return parse_json(send("POST", url, headers, {"json": body}).content)


def post_form(url, headers, form):
    """POST form as a web form (as OAuth token requests need) and return JSON."""
    return parse_json(send("POST", url, headers, {"form": form}).content)


def post_files(url, headers, form, files):
    """Upload files with the other form fields and return the JSON answer.

    files maps each field name to (file name, bytes, content type).
    """
    payload = {"form": form, "files": files}
    return parse_json(send("POST", url, headers, payload).content)


def put_bytes(url, headers, raw):
    """PUT raw bytes (for example an image) and return the Answer."""
    return send("PUT", url, headers, {"raw": raw})


def get_json(url, headers):
    """GET url and return the JSON answer."""
    return parse_json(send("GET", url, headers).content)


def get_bytes(url):
    """GET url (for example an image) and return the raw bytes."""
    return send("GET", url, {}).content
