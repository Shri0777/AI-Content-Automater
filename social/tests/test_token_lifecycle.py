"""Token refresh failures, refresh races and keeping users' tokens apart."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from core.crypto import decrypt_text
from core.errors import ProviderBusy
from notifications.models import Notification
from social.models import SocialAccount
from social.platforms import get_publisher
from social.publishers import PostContent
from social.tasks import refresh_social_tokens_task
from social.tests.linking import link_with_oauth
from social.tokens import REFRESH_BEFORE_POSTING, refresh_account, store_tokens
from tests.social_stubs import X_TOKEN_PATH, X_UPLOAD_PATH, add_x_routes


def expire_soon(account):
    """Make the account's token end in five minutes."""
    account.token_expires_at = timezone.now() + timedelta(minutes=5)
    account.save()


@pytest.fixture
def x_account(client, platforms):
    """A linked X account."""
    add_x_routes(platforms)
    link_with_oauth(client, "x")
    return SocialAccount.objects.get(platform="x")


def test_a_refused_refresh_marks_the_account_and_tells_the_owner(x_account, platforms):
    expire_soon(x_account)
    platforms.set_route("POST", X_TOKEN_PATH, {"status": 401, "json": {}})

    account = refresh_account(x_account.id, REFRESH_BEFORE_POSTING)

    assert account.status == "needs_reauth"
    notification = Notification.objects.get(kind="account_needs_reauth")
    assert notification.related_id == account.id


def test_a_busy_platform_leaves_the_account_as_it_was(x_account, platforms):
    expire_soon(x_account)
    platforms.set_route("POST", X_TOKEN_PATH, {"status": 503, "json": {}})

    with pytest.raises(ProviderBusy):
        refresh_account(x_account.id, REFRESH_BEFORE_POSTING)

    x_account.refresh_from_db()
    assert x_account.status == "active"
    assert decrypt_text(x_account.encrypted_refresh_token) == "refresh-1"


def test_the_background_job_refreshes_tokens_that_end_soon(x_account, platforms):
    expire_soon(x_account)

    assert refresh_social_tokens_task() == 1

    x_account.refresh_from_db()
    assert decrypt_text(x_account.encrypted_token) == "access-2"


def test_the_background_job_skips_a_busy_platform(x_account, platforms):
    expire_soon(x_account)
    platforms.set_route("POST", X_TOKEN_PATH, {"status": 503, "json": {}})

    assert refresh_social_tokens_task() == 0


class SlowTokens:
    """Answers token requests slowly, so two refreshes overlap in time."""

    def __init__(self, token_counter):
        self.token_counter = token_counter

    def answer(self, form):
        """Return the next tokens after a 0.3 second pause."""
        answer = self.token_counter.answer(form)
        answer["delay"] = 0.3
        return answer


def refresh_and_close(account_id):
    """Refresh in a worker thread, then close that thread's database link."""
    refresh_account(account_id, REFRESH_BEFORE_POSTING)
    connection.close()


def run_twice_at_once(account_id):
    """Run two refreshes of the same account at the same moment."""
    threads = []
    for _ in range(2):
        threads.append(threading.Thread(target=refresh_and_close, args=(account_id,)))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


@pytest.mark.django_db(transaction=True)
def test_two_workers_refreshing_at_once_use_the_refresh_token_only_once(
    user, platforms
):
    # Made directly (not linked): this test is about the refresh lock, and a
    # transactional test cannot rely on the limits other tests left behind.
    counter = add_x_routes(platforms)
    account = SocialAccount(user=user, platform="x", display_name="@a", external_id="1")
    store_tokens(account, counter.answer({})["json"])
    account.save()
    expire_soon(account)
    platforms.set_route("POST", X_TOKEN_PATH, SlowTokens(counter).answer)

    run_twice_at_once(account.id)

    assert len(platforms.requests_to(X_TOKEN_PATH)) == 1


def test_each_user_posts_only_with_their_own_token(
    client, api_client, other_user, platforms
):
    add_x_routes(platforms)
    link_with_oauth(client, "x")
    api_client.force_authenticate(other_user)
    link_with_oauth(api_client, "x")
    first = SocialAccount.objects.get(user__email="ada@example.com")
    second = SocialAccount.objects.get(user=other_user)

    get_publisher("x").publish(first, PostContent("one", b"P", ""))
    get_publisher("x").publish(second, PostContent("two", b"P", ""))

    used = [r["headers"]["Authorization"] for r in platforms.requests_to(X_UPLOAD_PATH)]
    assert used == ["Bearer access-1", "Bearer access-2"]
    assert decrypt_text(first.encrypted_token) == "access-1"
    assert decrypt_text(second.encrypted_token) == "access-2"


def test_users_cannot_see_or_unlink_each_others_accounts(
    client, api_client, other_user, x_account
):
    api_client.force_authenticate(other_user)

    listed = api_client.get("/api/v1/social/accounts/").json()
    deleted = api_client.delete(f"/api/v1/social/accounts/{x_account.id}/")

    assert listed == []
    assert deleted.status_code == 404
    assert SocialAccount.objects.filter(id=x_account.id).exists()
