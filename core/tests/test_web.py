"""Tests for the safe web client in core/web.py."""

import socket

import pytest

from core import web
from core.errors import (
    ProviderBusy,
    ProviderError,
    ProviderKeyRejected,
    ProviderNoAnswer,
)
from core.web import UnsafeAddress, check_address, get_json, post_json


def resolve_to(monkeypatch, ip_text):
    """Make every host name resolve to ip_text, like a DNS server would."""

    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip_text, 0))]

    monkeypatch.setattr(web.socket, "getaddrinfo", fake_getaddrinfo)


@pytest.mark.parametrize(
    "ip_text",
    [
        "127.0.0.1",  # this machine
        "10.0.0.5",  # private network
        "192.168.1.10",  # home network
        "172.17.0.2",  # Docker's network
        "169.254.169.254",  # cloud metadata service
        "100.64.0.1",  # carrier-grade NAT
        "0.0.0.0",  # "any address"
    ],
)
def test_addresses_that_lead_inside_a_network_are_refused(monkeypatch, ip_text):
    resolve_to(monkeypatch, ip_text)

    with pytest.raises(UnsafeAddress):
        check_address("https://innocent-looking.example.com/v1")


def test_a_public_address_is_allowed(monkeypatch):
    resolve_to(monkeypatch, "93.184.215.14")

    check_address("https://api.example.com/v1")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/v1",
        "file:///etc/passwd",
        "ftp://api.example.com",
        "https://user:pass@api.example.com",
        "not a url",
    ],
)
def test_only_plain_https_addresses_are_allowed(url):
    with pytest.raises(UnsafeAddress):
        check_address(url)


def test_a_json_answer_is_returned(stub_server):
    stub_server.set_route("POST", "/echo", {"json": {"ok": True}})

    answer = post_json(f"{stub_server.base_url}/echo", {}, {"question": 1})

    assert answer == {"ok": True}
    assert stub_server.requests[0]["body"] == {"question": 1}


@pytest.mark.parametrize(
    "status, error_class",
    [
        (401, ProviderKeyRejected),
        (403, ProviderKeyRejected),
        (429, ProviderBusy),
        (500, ProviderBusy),
        (503, ProviderBusy),
        (400, ProviderError),
        (404, ProviderError),
    ],
)
def test_each_failure_becomes_the_right_kind_of_error(stub_server, status, error_class):
    stub_server.set_route("GET", "/fail", {"status": status, "json": {}})

    with pytest.raises(error_class):
        get_json(f"{stub_server.base_url}/fail", {})


def test_redirects_are_never_followed(stub_server):
    stub_server.set_route("GET", "/moved", {"status": 302, "json": {}})

    with pytest.raises(ProviderError, match="redirect"):
        get_json(f"{stub_server.base_url}/moved", {})
    assert len(stub_server.requests) == 1


def test_an_answer_that_is_not_json_is_an_error(stub_server):
    stub_server.set_route("GET", "/html", {"body": b"<html>oops</html>"})

    with pytest.raises(ProviderError, match="not JSON"):
        get_json(f"{stub_server.base_url}/html", {})


def test_a_slow_service_is_reported_as_busy(stub_server, monkeypatch):
    monkeypatch.setattr(web, "TIMEOUT_SECONDS", 0.2)
    stub_server.set_route("GET", "/slow", {"delay": 1, "json": {}})

    with pytest.raises(ProviderBusy):
        get_json(f"{stub_server.base_url}/slow", {})


def test_a_huge_answer_is_refused(stub_server, monkeypatch):
    monkeypatch.setattr(web, "MAX_RESPONSE_BYTES", 100)
    stub_server.set_route("GET", "/huge", {"body": b"x" * 1000})

    with pytest.raises(ProviderError, match="more data"):
        get_json(f"{stub_server.base_url}/huge", {})


def test_the_api_key_is_hidden_in_error_messages(stub_server):
    key = "sk-very-secret-key-1234"
    stub_server.set_route(
        "GET", "/bad", {"status": 400, "json": {"error": f"bad key {key}"}}
    )

    with pytest.raises(ProviderError) as error:
        get_json(f"{stub_server.base_url}/bad", {"Authorization": f"Bearer {key}"})

    assert key not in str(error.value)
    assert "[hidden]" in str(error.value)


def test_a_web_form_is_sent_as_a_form(stub_server):
    stub_server.set_route("POST", "/token", {"json": {"access_token": "t"}})

    answer = web.post_form(f"{stub_server.base_url}/token", {}, {"code": "abc 1"})

    assert answer == {"access_token": "t"}
    request = stub_server.requests[0]
    assert request["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert request["form"] == {"code": "abc 1"}


def test_a_file_upload_sends_the_file_and_the_fields(stub_server):
    stub_server.set_route("POST", "/upload", {"json": {"data": {"id": "7"}}})

    answer = web.post_files(
        f"{stub_server.base_url}/upload",
        {},
        {"media_category": "tweet_image"},
        {"media": ("poster.png", b"PNGDATA", "image/png")},
    )

    assert answer == {"data": {"id": "7"}}
    request = stub_server.requests[0]
    assert request["headers"]["Content-Type"].startswith("multipart/form-data")
    assert b"PNGDATA" in request["raw_body"]
    assert b"tweet_image" in request["raw_body"]


def test_raw_bytes_can_be_put_and_the_answer_headers_are_returned(stub_server):
    stub_server.set_route(
        "PUT", "/file", {"status": 201, "body": b"", "headers": {"x-id": "abc"}}
    )

    answer = web.put_bytes(f"{stub_server.base_url}/file", {}, b"\x89PNG")

    assert answer.status == 201
    assert answer.headers["x-id"] == "abc"
    assert stub_server.requests[0]["raw_body"] == b"\x89PNG"


def test_post_json_with_headers_returns_the_answer_headers(stub_server):
    stub_server.set_route(
        "POST", "/posts", {"status": 201, "body": b"", "headers": {"x-id": "p1"}}
    )

    answer = web.send("POST", f"{stub_server.base_url}/posts", {}, {"json": {}})

    assert answer.headers["x-id"] == "p1"


def test_a_secret_sent_in_a_form_is_hidden_in_error_messages(stub_server):
    secret = "client-secret-abcdef"
    stub_server.set_route(
        "POST", "/token", {"status": 400, "json": {"error": f"bad {secret}"}}
    )

    with pytest.raises(ProviderError) as error:
        web.post_form(f"{stub_server.base_url}/token", {}, {"client_secret": secret})

    assert secret not in str(error.value)


def test_request_addresses_are_never_written_to_the_log(stub_server, caplog):
    stub_server.set_route("GET", "/token", {"json": {}})
    caplog.set_level("INFO")

    get_json(f"{stub_server.base_url}/token?client_secret=abcdefgh123", {})

    assert "abcdefgh123" not in caplog.text


def test_a_secret_in_the_address_is_hidden_in_error_messages(stub_server):
    secret = "app-secret-in-query-123"
    stub_server.set_route(
        "GET", "/token", {"status": 400, "json": {"error": f"bad {secret}"}}
    )

    with pytest.raises(ProviderError) as error:
        get_json(f"{stub_server.base_url}/token?client_secret={secret}", {})

    assert secret not in str(error.value)


def test_a_refused_connection_means_nothing_was_sent(stub_server):
    # Port 9 has nothing listening, so the connection is refused at once.
    with pytest.raises(ProviderBusy) as error:
        get_json("http://127.0.0.1:9/nothing", {})

    assert not isinstance(error.value, ProviderNoAnswer)


def test_a_request_that_gets_no_answer_may_have_been_acted_on(stub_server, monkeypatch):
    monkeypatch.setattr(web, "TIMEOUT_SECONDS", 0.2)
    stub_server.set_route("POST", "/slow", {"delay": 1, "json": {}})

    with pytest.raises(ProviderNoAnswer):
        post_json(f"{stub_server.base_url}/slow", {}, {})
