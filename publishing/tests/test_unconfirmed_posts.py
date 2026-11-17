"""Posts sent without an answer are never sent twice, and are settled safely."""

import threading
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from core import web
from notifications.models import Notification
from publishing.models import Publication
from publishing.reconcile import reconcile_ambiguous
from publishing.services import publish_post
from social.x_publisher import XPublisher
from tests.social_stubs import X_TWEETS_PATH

TWEET = {"data": {"id": "1445880548472328192", "text": "posted"}}


@pytest.fixture
def silent_platform(stub_server, monkeypatch):
    """X takes the tweet but answers after we stopped waiting."""
    monkeypatch.setattr(web, "TIMEOUT_SECONDS", 0.3)
    stub_server.set_route(
        "POST", X_TWEETS_PATH, {"status": 201, "json": TWEET, "delay": 1}
    )
    return stub_server


def settle_with_platform_answer(monkeypatch, outcome):
    """Make X's check_status give outcome for every unconfirmed post."""

    def answer(self, account, publication):
        return {"outcome": outcome, "external_id": "found-123"}

    monkeypatch.setattr(XPublisher, "check_status", answer)


def an_hour_from_now():
    """Return a moment well past CHECK_AFTER."""
    return timezone.now() + timedelta(hours=1)


def test_no_answer_marks_the_post_unconfirmed_not_failed(x_post, silent_platform):
    assert publish_post(x_post.id) == "publishing"

    publication = Publication.objects.get()
    assert publication.status == "ambiguous"
    notice = Notification.objects.get(kind="publish_unconfirmed")
    assert "@ada" in notice.message


def test_an_unconfirmed_post_is_never_sent_again(x_post, silent_platform):
    publish_post(x_post.id)
    publish_post(x_post.id)

    assert len(silent_platform.requests_to(X_TWEETS_PATH)) == 1


def test_a_platform_that_cannot_be_reached_is_a_plain_failure(x_post, settings):
    # Nothing listens on port 9 here, so the connection is refused at once.
    settings.SOCIAL_API_URLS = dict(settings.SOCIAL_API_URLS, x="http://127.0.0.1:9")

    assert publish_post(x_post.id) == "failed"
    assert Publication.objects.get().status == "failed"


def test_reconcile_settles_a_post_the_platform_confirms(
    x_post, silent_platform, monkeypatch
):
    publish_post(x_post.id)
    settle_with_platform_answer(monkeypatch, "published")

    assert reconcile_ambiguous(now=an_hour_from_now()) == 1

    publication = Publication.objects.get()
    assert publication.status == "published"
    assert publication.resolved_by == "platform"
    assert publication.external_id == "found-123"
    x_post.refresh_from_db()
    assert x_post.status == "published"


def test_a_post_the_platform_did_not_get_is_failed_not_resent(
    x_post, silent_platform, monkeypatch
):
    publish_post(x_post.id)
    settle_with_platform_answer(monkeypatch, "not_published")

    reconcile_ambiguous(now=an_hour_from_now())

    x_post.refresh_from_db()
    assert x_post.status == "failed"
    assert len(silent_platform.requests_to(X_TWEETS_PATH)) == 1


def test_when_the_platform_cannot_tell_the_owner_is_asked_once(x_post, silent_platform):
    publish_post(x_post.id)

    assert reconcile_ambiguous(now=an_hour_from_now()) == 0
    reconcile_ambiguous(now=an_hour_from_now())

    assert Publication.objects.get().status == "ambiguous"
    assert Notification.objects.filter(kind="publish_unconfirmed").count() == 1


def resolve_url(publication):
    """Return the address for settling a publication."""
    return f"/api/v1/publications/{publication.id}/resolve/"


def test_the_owner_can_confirm_it_went_out(x_post, silent_platform, api_client):
    publish_post(x_post.id)
    api_client.force_authenticate(x_post.user)
    publication = Publication.objects.get()

    response = api_client.post(
        resolve_url(publication), {"outcome": "published"}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["resolved_by"] == "user"
    x_post.refresh_from_db()
    assert x_post.status == "published"
    again = api_client.post(resolve_url(publication), {"outcome": "published"})
    assert again.status_code == 409


def test_nobody_else_can_settle_the_owners_post(x_post, silent_platform, api_client):
    publish_post(x_post.id)
    stranger = get_user_model().objects.create_user(
        email="grace@example.com", password="correct-horse-battery-staple"
    )
    api_client.force_authenticate(stranger)

    response = api_client.post(
        resolve_url(Publication.objects.get()), {"outcome": "published"}
    )

    assert response.status_code == 404
    assert Publication.objects.get().status == "ambiguous"


def publish_and_close(post_id, errors):
    """Publish in a worker thread, note any error, then close its database link."""
    try:
        publish_post(post_id)
    except Exception as error:  # noqa: BLE001 - the test checks there are none
        errors.append(error)
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_workers_publishing_at_once_make_one_call(x_post, stub_server):
    # A slow answer keeps the first worker busy while the second arrives.
    stub_server.set_route(
        "POST", X_TWEETS_PATH, {"status": 201, "json": TWEET, "delay": 0.3}
    )
    threads = []
    errors = []
    for _ in range(2):
        worker = threading.Thread(target=publish_and_close, args=(x_post.id, errors))
        threads.append(worker)

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(stub_server.requests_to(X_TWEETS_PATH)) == 1
    assert Publication.objects.count() == 1
    assert Notification.objects.filter(kind="post_published").count() == 1


def test_a_send_whose_worker_stopped_halfway_becomes_unconfirmed(x_post):
    post_version = x_post.final_version()
    account = x_post.plan.accounts.get()
    Publication.objects.create(
        post=x_post,
        version=post_version,
        account=account,
        idempotency_key="stuck",
        status="publishing",
    )

    reconcile_ambiguous(now=an_hour_from_now())

    assert Publication.objects.get().status == "ambiguous"
    assert Notification.objects.filter(kind="publish_unconfirmed").count() == 1
