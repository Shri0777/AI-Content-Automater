"""The nightly clean-up keeps only what the retention rules allow."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.utils import timezone

from core import disk
from core.maintenance import run_cleanup
from core.tasks import nightly_cleanup_task
from credentials.services import save_credential
from newsroom.ingest import ingest_active_presets, url_fingerprint
from newsroom.models import Article, ArticleUse
from planning.dispatcher import run_dispatcher
from planning.models import ContentPlan, PostSlot, Topic
from quotas.models import QuotaOverride
from social.models import LinkAttempt, SocialAccount
from studio.models import GenerationStep, Post, PostVersion
from studio.runner import run_stage

LATER = timedelta(days=31)


@pytest.fixture
def plan(db):
    """A plan with one demo account and one AI news topic."""
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
    Topic.objects.create(plan=plan, name="AI", preset="ai_news")
    return plan


@pytest.fixture
def made_post(plan):
    """A post run through every stage, with poster and artwork files."""
    post = Post.objects.create(
        user=plan.user, plan=plan, topic=plan.topics.get(), demo_mode=True
    )
    for _ in range(6):
        run_stage(post.id)
    return post


def test_old_poster_files_are_deleted_but_the_words_are_kept(made_post, api_client):
    version = made_post.final_version()
    poster, artwork = version.poster_path, version.artwork_path

    counts = run_cleanup(now=timezone.now() + LATER)

    version.refresh_from_db()
    assert counts["images_expired"] == 1
    assert version.image_expired is True
    assert not default_storage.exists(poster)
    assert not default_storage.exists(artwork)
    assert version.caption != ""
    api_client.force_authenticate(made_post.user)
    response = api_client.get(f"/api/v1/posts/{made_post.id}/poster/")
    assert response.status_code == 404
    assert "retention" in response.json()["detail"]


def test_recent_posters_and_longer_user_limits_are_respected(made_post):
    QuotaOverride.objects.create(
        user=made_post.user, resource="poster_retention_days", limit_value=60
    )

    assert run_cleanup(now=timezone.now() + LATER)["images_expired"] == 0
    assert run_cleanup(now=timezone.now())["images_expired"] == 0
    assert PostVersion.objects.filter(image_expired=True).count() == 0


def store_article(title, stored_days_ago):
    """Save an article stored stored_days_ago days ago."""
    url = f"https://example.com/{title}"
    return Article.objects.create(
        url_hash=url_fingerprint(url),
        url=url,
        title=title,
        source_name="Example",
        preset="ai_news",
        published_at=timezone.now(),
        stored_at=timezone.now() - timedelta(days=stored_days_ago),
        text="Some working text.",
    )


def test_old_article_text_is_cleared_and_old_unused_articles_go(plan):
    fresh = store_article("fresh", 1)
    old_text = store_article("old-text", 20)
    old_used = store_article("old-used", 100)
    store_article("old-unused", 100)
    ArticleUse.objects.create(plan=plan, article=old_used)

    counts = run_cleanup()

    fresh.refresh_from_db()
    old_text.refresh_from_db()
    assert fresh.text == "Some working text."
    assert old_text.text == ""
    assert counts["articles_deleted"] == 1
    assert Article.objects.filter(title="old-used").exists()


def test_old_records_and_unfinished_link_attempts_are_deleted(made_post):
    attempt = LinkAttempt.objects.create(
        user=made_post.user, platform="x", state_hash="h", encrypted_code_verifier="v"
    )
    LinkAttempt.objects.filter(id=attempt.id).update(
        created_at=timezone.now() - timedelta(days=2)
    )
    steps = GenerationStep.objects.filter(post=made_post).count()

    counts = run_cleanup(now=timezone.now() + timedelta(days=91))

    assert counts["steps_deleted"] == steps
    assert counts["link_attempts_deleted"] == 1


def test_the_nightly_task_runs_the_cleanup(db):
    assert set(nightly_cleanup_task()) == {
        "images_expired",
        "article_texts_cleared",
        "articles_deleted",
        "steps_deleted",
        "link_attempts_deleted",
        "budgets_deleted",
    }


def disk_this_full(monkeypatch, share):
    """Pretend the media disk is share full (0.0 to 1.0)."""

    def fake_share():
        return share

    monkeypatch.setattr(disk, "disk_used_share", fake_share)


def test_a_nearly_full_disk_stops_new_posts_and_news(plan, monkeypatch):
    disk_this_full(monkeypatch, 0.95)
    publish_at = timezone.now() + timedelta(minutes=30)
    PostSlot.objects.create(plan=plan, publish_at=publish_at, generate_at=publish_at)

    assert run_dispatcher(now=publish_at)["started"] == 0
    assert ingest_active_presets() == 0
    assert PostSlot.objects.get().status == "waiting"


def test_a_filling_disk_only_warns(plan, monkeypatch, caplog):
    disk_this_full(monkeypatch, 0.85)
    publish_at = timezone.now() + timedelta(minutes=30)
    PostSlot.objects.create(plan=plan, publish_at=publish_at, generate_at=publish_at)

    assert run_dispatcher(now=publish_at)["started"] == 1
    assert "85% full" in caplog.text
