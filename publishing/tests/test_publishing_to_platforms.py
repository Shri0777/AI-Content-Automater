"""Publishing an approved post to real platform adapters on a stub server."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time

from credentials.services import save_credential
from notifications.models import Notification
from planning.models import ContentPlan, Topic
from publishing.models import Publication
from publishing.services import publish_post
from social.models import SocialAccount
from social.tokens import store_tokens
from studio.models import Post
from studio.public_links import make_public_poster_url
from studio.runner import run_stage
from studio.statuses import change_status
from tests.social_stubs import (
    X_TOKEN_PATH,
    X_TWEETS_PATH,
    add_x_routes,
    point_settings_at,
)


@pytest.fixture
def x_post(db, stub_server, settings):
    """An approved demo post for a plan that posts to one linked X account."""
    point_settings_at(settings, stub_server)
    add_x_routes(stub_server)
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    account = SocialAccount(
        user=user, platform="x", network="x", display_name="@ada", external_id="1"
    )
    store_tokens(
        account,
        {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expires_in": 7200,
        },
    )
    account.save()
    plan = ContentPlan.objects.create(user=user, name="Tech news")
    plan.accounts.add(account)
    topic = Topic.objects.create(plan=plan, name="Tips", preset="linux_tips")
    post = Post.objects.create(user=user, plan=plan, topic=topic, demo_mode=True)
    for _ in ["researching", "drafting", "imaging", "reviewing"]:
        run_stage(post.id)
    post.refresh_from_db()
    change_status(post, "approved")
    return post


def test_an_approved_post_reaches_x_within_its_caption_limit(x_post, stub_server):
    assert publish_post(x_post.id) == "published"

    tweet = stub_server.requests_to(X_TWEETS_PATH)[0]["body"]
    assert len(tweet["text"]) <= 280
    assert tweet["text"].endswith(x_post.plan.ai_label_text)
    publication = Publication.objects.get()
    assert publication.external_id == "1445880548472328192"


def test_a_token_that_ends_soon_is_refreshed_before_posting(x_post, stub_server):
    account = x_post.plan.accounts.get()
    account.token_expires_at = timezone.now() + timedelta(minutes=2)
    account.save()

    publish_post(x_post.id)

    assert len(stub_server.requests_to(X_TOKEN_PATH)) == 1
    tweet_request = stub_server.requests_to(X_TWEETS_PATH)[0]
    assert tweet_request["headers"]["Authorization"] == "Bearer access-1"


def test_a_refused_token_marks_the_account_for_reconnecting(x_post, stub_server):
    stub_server.set_route("POST", X_TWEETS_PATH, {"status": 401, "json": {}})

    assert publish_post(x_post.id) == "failed"

    account = x_post.plan.accounts.get()
    assert account.status == "needs_reauth"
    assert Notification.objects.filter(kind="account_needs_reauth").count() == 1
    assert "refused" in Publication.objects.get().error


def test_an_account_that_needs_reconnecting_is_not_posted_to(x_post, stub_server):
    x_post.plan.accounts.update(status="needs_reauth")

    assert publish_post(x_post.id) == "failed"
    assert stub_server.requests_to(X_TWEETS_PATH) == []


def test_a_public_poster_link_serves_the_png_without_a_login(x_post, api_client):
    link = make_public_poster_url(x_post.latest_version())
    path = link.split("8000", 1)[1]

    response = api_client.get(path)

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_a_changed_poster_link_is_refused(x_post, api_client):
    path = make_public_poster_url(x_post.latest_version()).split("8000", 1)[1]

    response = api_client.get(path.replace(".png", "x.png"))

    assert response.status_code == 404


def test_a_poster_link_stops_working_after_a_week(x_post, api_client):
    path = make_public_poster_url(x_post.latest_version()).split("8000", 1)[1]

    with freeze_time(timezone.now() + timedelta(days=8)):
        response = api_client.get(path)

    assert response.status_code == 404
