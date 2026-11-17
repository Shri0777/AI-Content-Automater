"""The OAuth link flow refuses replays, old attempts and forged callbacks."""

from datetime import timedelta

from freezegun import freeze_time

from quotas.models import QuotaOverride
from social.models import LinkAttempt, SocialAccount
from social.tests.linking import finish_link, start_link
from tests.social_stubs import X_TOKEN_PATH, add_x_routes


def test_linking_needs_a_login(api_client, platforms):
    response = api_client.post("/api/v1/social/link/x/start/")

    assert response.status_code == 401


def test_a_platform_without_an_app_cannot_be_linked(client, platforms, settings):
    settings.SOCIAL_APPS = {"x": {"client_id": "", "client_secret": ""}}

    response = client.post("/api/v1/social/link/x/start/")

    assert response.status_code == 400
    assert response.json()["code"] == "platform_not_ready"


def test_an_unknown_platform_cannot_be_linked(client, platforms):
    response = client.post("/api/v1/social/link/myspace/start/")

    assert response.json()["code"] == "platform_not_ready"


def test_only_a_fingerprint_of_the_state_is_stored(client, platforms):
    approval = start_link(client, "x")

    attempt = LinkAttempt.objects.get()
    assert approval["state"] not in attempt.state_hash
    assert len(attempt.state_hash) == 64


def test_a_callback_can_be_used_only_once(client, platforms):
    add_x_routes(platforms)
    approval = start_link(client, "x")
    params = {"code": "code-123", "state": approval["state"]}

    first = finish_link("x", params)
    replay = finish_link("x", params)

    assert "result=linked" in first["Location"]
    assert "reason=link_failed" in replay["Location"]
    assert len(platforms.requests_to(X_TOKEN_PATH)) == 1


def test_a_made_up_state_links_nothing(client, platforms):
    add_x_routes(platforms)
    start_link(client, "x")

    response = finish_link("x", {"code": "code-123", "state": "guessed"})

    assert "reason=link_failed" in response["Location"]
    assert platforms.requests_to(X_TOKEN_PATH) == []


def test_an_attempt_older_than_ten_minutes_is_refused(client, platforms):
    add_x_routes(platforms)
    approval = start_link(client, "x")
    later = LinkAttempt.objects.get().created_at + timedelta(minutes=11)

    with freeze_time(later):
        response = finish_link("x", {"code": "c", "state": approval["state"]})

    assert "reason=link_failed" in response["Location"]


def test_a_state_for_one_platform_cannot_finish_another(client, platforms):
    add_x_routes(platforms)
    approval = start_link(client, "x")

    response = finish_link("linkedin", {"code": "c", "state": approval["state"]})

    assert "reason=link_failed" in response["Location"]


def test_a_cancelled_approval_sends_the_user_back_without_linking(client, platforms):
    approval = start_link(client, "x")

    response = finish_link("x", {"error": "access_denied", "state": approval["state"]})

    assert response.status_code == 302
    assert response["Location"].startswith("http://localhost:5173/social/")
    assert "result=cancelled" in response["Location"]
    assert not SocialAccount.objects.exists()


def test_the_account_limit_is_checked_before_and_after_approval(
    client, platforms, user
):
    add_x_routes(platforms)
    approval = start_link(client, "x")
    QuotaOverride.objects.create(user=user, resource="social_accounts", limit_value=0)

    response = finish_link("x", {"code": "c", "state": approval["state"]})
    refused_start = client.post("/api/v1/social/link/x/start/")

    assert "reason=quota_exceeded" in response["Location"]
    assert not SocialAccount.objects.exists()
    assert refused_start.status_code == 403
    assert refused_start.json()["code"] == "quota_exceeded"
