"""Connect only to public addresses, checked at the moment of connecting.

core/web.py checks an address before a request, but the request then looks
the host name up again. A hostile DNS server can answer "a public address"
the first time and "127.0.0.1" the second time ("DNS rebinding"), and the
request would reach our own network.

So every connection goes through CheckedNetwork below: it looks the host up
once, refuses if any of its addresses is private, and then connects to that
exact checked address. Encryption (TLS) still checks the certificate against
the host name, so this changes nothing for real services.

Named exception to the code standard: this is the only file that uses the
httpcore library (the engine inside httpx), because httpx offers no public
way to do this.
"""

import ipaddress
import socket

import httpcore
import httpx
from django.conf import settings

from core.errors import ProviderError


class UnsafeAddress(ProviderError):
    """Raised for an address we refuse to contact."""


def look_up(host):
    """Return every IP address of host, from one DNS look-up."""
    try:
        results = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ProviderError(f"The address {host} could not be found.") from None
    addresses = []
    for result in results:
        addresses.append(result[4][0].split("%")[0])
    return addresses


def public_address_of(host):
    """Return one IP address of host, or raise UnsafeAddress if any is private."""
    addresses = look_up(host)
    if not settings.ALLOW_PRIVATE_PROVIDER_URLS:
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise UnsafeAddress(
                    f"{host} leads to a private network address, which is not allowed."
                )
    return addresses[0]


class CheckedNetwork(httpcore.SyncBackend):
    """Opens connections only to addresses checked at connect time."""

    def connect_tcp(  # noqa: PLR0913 - httpcore decides this method's shape
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        """Look host up once, check it, and connect to that exact address."""
        address = public_address_of(host)
        return super().connect_tcp(
            address, port, timeout, local_address, socket_options
        )


def checked_transport():
    """Return an httpx transport whose every connection is checked."""
    transport = httpx.HTTPTransport(trust_env=False)
    # httpx has no public option for a network backend, so its connection
    # pool is replaced with one that uses ours. core/tests/test_safe_network.py
    # fails if an httpx update changes this.
    transport._pool = httpcore.ConnectionPool(
        ssl_context=httpx.create_ssl_context(),
        network_backend=CheckedNetwork(),
    )
    return transport
