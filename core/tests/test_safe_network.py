"""Connections are checked when they are made, which stops DNS rebinding."""

import pytest

from core import safe_network, web
from core.safe_network import CheckedNetwork, UnsafeAddress, checked_transport


class FlippingDns:
    """A hostile DNS server: a public address first, then this machine."""

    def __init__(self):
        self.calls = 0

    def look_up(self, host):
        """Answer a look-up, flipping to this machine after the first one."""
        self.calls = self.calls + 1
        if self.calls == 1:
            return ["93.184.215.14"]
        return ["127.0.0.1"]


def test_an_address_that_turns_private_after_the_first_check_is_refused(
    monkeypatch, settings
):
    settings.ALLOW_PRIVATE_PROVIDER_URLS = False
    dns = FlippingDns()
    monkeypatch.setattr(safe_network, "look_up", dns.look_up)

    with pytest.raises(UnsafeAddress):
        web.get_json("https://rebind.example/secrets", {})

    # Checked once before the request, and again when connecting.
    assert dns.calls == 2


def test_the_connection_goes_to_the_address_that_was_checked(stub_server, monkeypatch):
    port = stub_server.base_url.rsplit(":", 1)[1]
    stub_server.set_route("GET", "/hello", {"json": {"hi": True}})

    def only_this_machine(host):
        return ["127.0.0.1"]

    monkeypatch.setattr(safe_network, "look_up", only_this_machine)

    answer = web.get_json(f"http://made-up-name.test:{port}/hello", {})

    assert answer == {"hi": True}


def test_every_request_uses_the_checked_network():
    transport = checked_transport()

    assert isinstance(transport._pool._network_backend, CheckedNetwork)
