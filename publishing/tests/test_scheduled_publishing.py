"""Scheduled posts are published at their time, and expire if never approved."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from credentials.services import save_credential
from notifications.models import Notification
from planning.dispatcher import run_dispatcher
from planning.models import ContentPlan, PostSlot, Topic
from publishing.models import Publication
from publishing.scheduled import expire_late_approvals, publish_due_posts
from social.models import SocialAccount
from studio.models import Post
from studio.runner import run_stage
from studio.services import approve_post


@pytest.fixture
def plan(db):
    """A plan that posts to one demo account."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    plan = ContentPlan.objects.create(user=user, name="Tech news")
    plan.accounts.add(
        SocialAccount.objects.create(
            user=user, platform="demo", display_name="Demo", external_id="d1"
        )
    )
    Topic.objects.create(plan=plan, name="Tips", preset="linux_tips")
    return plan


def make_scheduled_post(plan, publish_in):
    """Start a slot publishing publish_in from now; return its post (made)."""
    publish_at = timezone.now() + publish_in
    PostSlot.objects.create(
        plan=plan, publish_at=publish_at, generate_at=publish_at - timedelta(hours=1)
    )
    run_dispatcher()
    post = Post.objects.get()
    assert post.status == "awaiting_approval"
    return post


def test_an_approved_post_waits_for_its_time(plan):
    post = make_scheduled_post(plan, timedelta(minutes=30))

    approve_post(plan.user, post.id)

    post.refresh_from_db()
    assert post.status == "approved"
    assert not Publication.objects.exists()
    assert publish_due_posts() == 0


def test_an_approved_post_is_published_when_its_time_comes(plan):
    post = make_scheduled_post(plan, timedelta(minutes=30))
    approve_post(plan.user, post.id)

    published = publish_due_posts(now=timezone.now() + timedelta(minutes=31))

    assert published == 1
    post.refresh_from_db()
    assert post.status == "published"
    assert Publication.objects.count() == 1


def test_publishing_due_posts_twice_still_posts_once(plan):
    post = make_scheduled_post(plan, timedelta(minutes=30))
    approve_post(plan.user, post.id)
    later = timezone.now() + timedelta(minutes=31)

    publish_due_posts(now=later)
    publish_due_posts(now=later)

    assert Publication.objects.count() == 1


def test_a_post_not_approved_in_time_expires_and_the_owner_is_told(plan):
    post = make_scheduled_post(plan, timedelta(minutes=30))
    # 30 minutes to its time, plus the plan's 30 minutes of allowed lateness.
    after_deadline = timezone.now() + timedelta(minutes=61)

    assert expire_late_approvals(now=after_deadline) == 1

    post.refresh_from_db()
    assert post.status == "expired"
    assert Notification.objects.filter(kind="post_expired").count() == 1


def test_a_post_is_not_expired_before_its_deadline(plan):
    make_scheduled_post(plan, timedelta(minutes=30))

    assert expire_late_approvals(now=timezone.now() + timedelta(minutes=45)) == 0


def test_a_hold_plan_keeps_a_late_post_and_publishes_it_once_approved(plan):
    plan.on_missed_approval = "hold"
    plan.save()
    post = make_scheduled_post(plan, timedelta(minutes=30))

    assert expire_late_approvals(now=timezone.now() + timedelta(days=1)) == 0
    PostSlot.objects.update(publish_at=timezone.now() - timedelta(hours=2))
    approve_post(plan.user, post.id)

    post.refresh_from_db()
    assert post.status == "published"


def test_a_generate_now_post_is_published_as_soon_as_it_is_approved(plan):
    topic = plan.topics.get()
    post = Post.objects.create(user=plan.user, plan=plan, topic=topic, demo_mode=True)
    for _ in ["researching", "drafting", "imaging", "reviewing"]:
        run_stage(post.id)

    approve_post(plan.user, post.id)

    post.refresh_from_db()
    assert post.status == "published"
