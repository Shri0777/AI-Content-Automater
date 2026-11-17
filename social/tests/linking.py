"""Helpers that link accounts through the API the way a browser would."""

from urllib.parse import parse_qs, urlsplit

from rest_framework.test import APIClient


def query_of(url):
    """Return the query values of url as a dict of single values."""
    values = parse_qs(urlsplit(url).query)
    result = {}
    for name, value_list in values.items():
        result[name] = value_list[0]
    return result


def start_link(client, platform):
    """Start linking; return the approval page's query values."""
    response = client.post(f"/api/v1/social/link/{platform}/start/")
    assert response.status_code == 200, response.json()
    return query_of(response.json()["authorization_url"])


def finish_link(platform, params):
    """Call the callback like the platform would, and return the response.

    The user comes back from the platform's website, so the request has no
    login: a fresh client without one is used.
    """
    url = f"/api/v1/social/link/{platform}/callback/"
    return APIClient().get(url, params)


def link_with_oauth(client, platform):
    """Run a whole link (start, approve, callback); return the callback response."""
    approval = start_link(client, platform)
    return finish_link(platform, {"code": "code-123", "state": approval["state"]})
