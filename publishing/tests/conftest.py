"""Shared setup for the publishing tests: an approved post for an X account."""

import pytest
from django.contrib.auth import get_user_model

from credentials.services import save_credential
from planning.models import ContentPlan, Topic
from social.models import SocialAccount
from social.tokens import store_tokens
from studio.models import Post
from studio.runner import run_stage
from studio.statuses import change_status
from tests.social_stubs import add_x_routes, point_settings_at


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
