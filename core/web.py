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

Known gap: the host is resolved before connecting, and a hostile DNS server
could answer differently a moment later ("DNS rebinding"). Closing that gap
is part of the security work in Phase 9.
"""

import ipaddress
import json
import socket
from urllib.parse import urlsplit

import httpx
from django.conf import settings

from core.errors import ProviderBusy, ProviderError, ProviderKeyRejected

TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
KEY_REJECTED_STATUSES = [401, 403]
TRY_LATER_STATUSES = [408, 409, 425, 429, 500, 502, 503, 504]
MAX_ERROR_TEXT = 300


class UnsafeAddress(ProviderError):
    """Raised for an address we refuse to contact."""


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
    """Raise UnsafeAddress unless every IP address of url's host is public."""
    host = check_url_format(url)
    if settings.ALLOW_PRIVATE_PROVIDER_URLS:
        return
    try:
        results = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ProviderError(f"The address {host} could not be found.") from None
    for result in results:
        ip_text = result[4][0].split("%")[0]
        if not ipaddress.ip_address(ip_text).is_global:
            raise UnsafeAddress(
                f"{host} leads to a private network address, which is not allowed."
            )


def hide_secrets(text, headers):
    """Return text with any secret from the request headers replaced."""
    for value in headers.values():
        secret = value.split(" ")[-1]
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


def check_status(status, content, url, headers):
    """Raise the right error for a status code that is not a success."""
    if status < 300:
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
        raise ProviderError(f"{host} tried to redirect us, which is not allowed.")
    detail = content.decode(errors="replace")[:MAX_ERROR_TEXT]
    raise ProviderError(
        f"{host} refused the request (HTTP {status}): {hide_secrets(detail, headers)}"
    )


def send(method, url, headers, body=None):
    """Send one request and return the response body as bytes."""
    check_address(url)
    try:
        with httpx.Client(
            timeout=TIMEOUT_SECONDS, follow_redirects=False, trust_env=False
        ) as client:
            with client.stream(method, url, headers=headers, json=body) as response:
                content = read_limited(response)
    except httpx.TimeoutException:
        raise ProviderBusy("The service took too long to answer.") from None
    except httpx.TransportError:
        raise ProviderBusy("The service could not be reached.") from None
    check_status(response.status_code, content, url, headers)
    return content


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
    return parse_json(send("POST", url, headers, body))


def get_json(url, headers):
    """GET url and return the JSON answer."""
    return parse_json(send("GET", url, headers))


def get_bytes(url):
    """GET url (for example an image) and return the raw bytes."""
    return send("GET", url, {})
