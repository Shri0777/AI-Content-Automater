"""Tests for publishing approved posts and adding the AI label."""

import pytest
from django.contrib.auth import get_user_model

from core.errors import ProviderError
from credentials.services import save_credential
from demo.publisher import DemoPublisher
from planning.models import ContentPlan, Topic
from publishing.models import Publication
from publishing.services import add_ai_label, publish_post
from publishing.tasks import publish_post_task
from social.models import SocialAccount
from studio.models import Post
from studio.pipeline import run_stage
from studio.statuses import change_status

LABEL = "Made with AI assistance."


def test_a_short_caption_gets_the_label_added():
    assert add_ai_label("Hello", LABEL, 100) == f"Hello\n\n{LABEL}"


def test_a_long_caption_is_shortened_so_the_label_is_never_cut():
    result = add_ai_label("word " * 100, LABEL, 60)

    assert len(result) <= 60
    assert result.endswith(LABEL)
    assert "…" in result


def test_no_label_means_the_caption_is_only_shortened():
    assert add_ai_label("abcdef", "", 3) == "abc"


@pytest.fixture
def approved_post(db):
    """A post for a plan with two demo accounts, made and approved."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    plan = ContentPlan.objects.create(user=user, name="Tech news")
    for number in [1, 2]:
        plan.accounts.add(
            SocialAccount.objects.create(
                user=user,
                platform="demo",
                display_name=f"Account {number}",
                external_id=f"a{number}",
            )
        )
    topic = Topic.objects.create(plan=plan, name="Tips", preset="linux_tips")
    post = Post.objects.create(user=user, plan=plan, topic=topic, demo_mode=True)
    for _ in ["researching", "drafting", "imaging", "reviewing"]:
        run_stage(post.id)
    post.refresh_from_db()
    assert post.status == "awaiting_approval"
    change_status(post, "approved")
    return post


def test_the_label_is_on_the_caption_sent_to_the_platform(approved_post, monkeypatch):
    sent_captions = []

    def remember_caption(self, account, caption, image_bytes):
        sent_captions.append(caption)
        return "demo-post-1"

    monkeypatch.setattr(DemoPublisher, "publish", remember_caption)

    publish_post(approved_post.id)

    assert sent_captions[0].endswith(LABEL)


def test_publishing_twice_contacts_each_platform_only_once(approved_post):
    publish_post(approved_post.id)
    publish_post(approved_post.id)

    assert Publication.objects.count() == 2


def test_one_failing_account_does_not_stop_the_others(approved_post, monkeypatch):
    def fail_for_account_2(self, account, caption, image_bytes):
        if account.display_name == "Account 2":
            raise ProviderError("Account 2 was refused.")
        return "demo-post-1"

    monkeypatch.setattr(DemoPublisher, "publish", fail_for_account_2)

    assert publish_post(approved_post.id) == "published"
    approved_post.refresh_from_db()
    assert approved_post.status_reason == "Could not publish to: Account 2."


def test_a_post_fails_when_no_account_gets_it(approved_post, monkeypatch):
    def always_fail(self, account, caption, image_bytes):
        raise ProviderError("Refused.")

    monkeypatch.setattr(DemoPublisher, "publish", always_fail)

    assert publish_post(approved_post.id) == "failed"


def test_a_post_fails_when_its_plan_has_no_accounts(approved_post):
    approved_post.plan.accounts.clear()

    assert publish_post(approved_post.id) == "failed"


def test_a_bug_while_publishing_fails_the_post_instead_of_leaving_it_stuck(
    approved_post, monkeypatch
):
    def crash(post, version, account):
        raise RuntimeError("A bug in the caption code.")

    monkeypatch.setattr("publishing.services.caption_for", crash)

    with pytest.raises(RuntimeError):
        publish_post_task.delay(str(approved_post.id))

    approved_post.refresh_from_db()
    assert approved_post.status == "failed"
