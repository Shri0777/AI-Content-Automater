"""Approval end to end: auto mode, editing a caption, and every notification."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.errors import ProviderKeyRejected
from credentials.services import save_credential
from demo.text_model import DemoTextModel
from notifications.models import KIND_CHOICES, Notification
from planning.models import ContentPlan, PostSlot, Topic
from publishing.models import Publication
from social.models import SocialAccount
from studio.models import Post
from studio.runner import run_stage

PROJECT_FOLDER = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def plan(db):
    """An "auto" plan on AI news that posts to one demo account."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    plan = ContentPlan.objects.create(user=user, name="Tech news", approval_mode="auto")
    plan.accounts.add(
        SocialAccount.objects.create(
            user=user, platform="demo", display_name="Demo", external_id="d1"
        )
    )
    Topic.objects.create(plan=plan, name="AI", preset="ai_news")
    return plan


def make_post(plan, slot=None):
    """Run a new post through every stage; return it reloaded."""
    post = Post.objects.create(
        user=plan.user, plan=plan, topic=plan.topics.get(), slot=slot, demo_mode=True
    )
    for _ in range(10):
        run_stage(post.id)
    post.refresh_from_db()
    return post


def test_an_auto_plan_publishes_a_clean_post_without_asking(plan):
    post = make_post(plan)

    assert post.status == "published"
    assert Publication.objects.filter(post=post, status="published").count() == 1
    assert not Notification.objects.filter(kind="post_awaiting_approval").exists()


def test_an_auto_plan_waits_for_the_slot_time_before_publishing(plan):
    publish_at = timezone.now() + timedelta(hours=1)
    slot = PostSlot.objects.create(
        plan=plan, publish_at=publish_at, generate_at=publish_at, status="started"
    )

    post = make_post(plan, slot)

    assert post.status == "approved"
    assert not Publication.objects.exists()


def test_a_post_below_the_minimum_score_waits_and_says_why(plan):
    plan.auto_post_min_score = 30
    plan.save()

    post = make_post(plan)

    assert post.status == "awaiting_approval"
    notice = Notification.objects.get(kind="post_awaiting_approval")
    assert "below this plan's minimum" in notice.message


def test_a_manual_plan_always_asks(plan):
    plan.approval_mode = "manual"
    plan.save()

    assert make_post(plan).status == "awaiting_approval"


@pytest.fixture
def waiting_post(plan):
    """A post on a manual plan, waiting for approval."""
    plan.approval_mode = "manual"
    plan.save()
    return make_post(plan)


def test_the_owner_can_reword_a_post_before_approving_it(waiting_post, api_client):
    api_client.force_authenticate(waiting_post.user)

    response = api_client.patch(
        f"/api/v1/posts/{waiting_post.id}/",
        {"headline": "My own headline", "caption": "My own words."},
        format="json",
    )

    assert response.status_code == 200
    final = waiting_post.final_version()
    assert final.edited_by_user is True
    assert final.caption == "My own words."
    assert final.artwork_path == waiting_post.versions.get(number=1).artwork_path
    api_client.post(f"/api/v1/posts/{waiting_post.id}/approve/")
    publication = Publication.objects.get(post=waiting_post)
    assert publication.version == final


def test_a_published_post_cannot_be_reworded(waiting_post, api_client):
    api_client.force_authenticate(waiting_post.user)
    api_client.post(f"/api/v1/posts/{waiting_post.id}/approve/")

    response = api_client.patch(
        f"/api/v1/posts/{waiting_post.id}/", {"caption": "Too late."}, format="json"
    )

    assert response.status_code == 409


def test_a_refused_key_pauses_the_plans_and_says_so(plan, monkeypatch):
    def refuse(self, articles, requirements):
        # As ask_safely() does, note which credential the provider refused.
        error = ProviderKeyRejected("The key was refused.")
        error.credential = self.credential
        raise error

    monkeypatch.setattr(DemoTextModel, "score_articles", refuse)
    make_post(plan)

    plan.refresh_from_db()
    assert plan.paused is True
    notice = Notification.objects.get(kind="plan_paused")
    assert "text API key was refused" in notice.message


def test_every_notification_kind_is_sent_somewhere_in_the_code():
    code = ""
    for path in PROJECT_FOLDER.rglob("*.py"):
        skipped = ["tests", "migrations", ".venv", "venv"]
        if any(part in path.parts for part in skipped):
            continue
        code = code + path.read_text()

    unused = []
    for kind, _ in KIND_CHOICES:
        if f'"{kind}"' not in code.replace("KIND_CHOICES", ""):
            unused.append(kind)
    assert unused == []
