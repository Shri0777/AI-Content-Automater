"""Tests for the fixed rules of the studio: statuses, verdicts and posters."""

from io import BytesIO

import pytest
from PIL import Image

from core.errors import ProviderError
from demo.image_model import DemoImageModel
from notifications.models import Notification
from studio.models import STATUS_CHOICES, Post
from studio.pipeline import run_stage
from studio.posters import draw_abstract_artwork, render_poster
from studio.statuses import (
    ALLOWED_TRANSITIONS,
    StatusChangeNotAllowed,
    change_status,
    fail_after_crash,
)
from studio.tasks import advance_post_task
from studio.verdicts import decide_verdict

GOOD_SCORES = {"grounding": 5, "relevance": 4, "clarity": 4, "tone": 5, "safety": 5}


def test_every_status_has_an_entry_in_the_transition_table():
    statuses = [value for value, label in STATUS_CHOICES]

    assert sorted(ALLOWED_TRANSITIONS) == sorted(statuses)
    for next_statuses in ALLOWED_TRANSITIONS.values():
        for status in next_statuses:
            assert status in statuses


@pytest.mark.parametrize(
    "scores, issues, verdict",
    [
        (GOOD_SCORES, [], "pass"),
        ({"grounding": 5, "clarity": 3}, [], "revise"),
        (GOOD_SCORES, [{"severity": "minor"}], "pass"),
        (GOOD_SCORES, [{"severity": "blocker"}], "reject"),
        ({}, [], "revise"),
    ],
)
def test_the_verdict_follows_fixed_rules(scores, issues, verdict):
    assert decide_verdict(scores, issues) == verdict


def test_a_post_cannot_skip_ahead(plan):
    post = Post.objects.create(user=plan.user, plan=plan)

    with pytest.raises(StatusChangeNotAllowed):
        change_status(post, "published")


def test_only_one_of_two_racing_changes_wins(plan):
    post = Post.objects.create(user=plan.user, plan=plan, status="awaiting_approval")
    first_copy = Post.objects.get(id=post.id)
    second_copy = Post.objects.get(id=post.id)

    change_status(first_copy, "approved")

    with pytest.raises(StatusChangeNotAllowed):
        change_status(second_copy, "rejected")
    assert Post.objects.get(id=post.id).status == "approved"


def test_the_poster_keeps_the_artwork_size():
    artwork = draw_abstract_artwork("seed", 640, 480)

    poster = render_poster(artwork, "A long headline " * 10, "Source: Demo")

    assert Image.open(BytesIO(poster)).size == (640, 480)


def test_the_same_prompt_always_draws_the_same_artwork():
    assert draw_abstract_artwork("a", 64, 64) == draw_abstract_artwork("a", 64, 64)
    assert draw_abstract_artwork("a", 64, 64) != draw_abstract_artwork("b", 64, 64)


def test_a_provider_failure_fails_the_post_and_tells_the_user(
    client, plan, monkeypatch
):
    def broken_artwork(self, prompt, width, height):
        raise ProviderError("The image service is down.")

    monkeypatch.setattr(DemoImageModel, "make_artwork", broken_artwork)

    post_id = client.post(f"/api/v1/plans/{plan.id}/generate-now/").json()["id"]

    post = client.get(f"/api/v1/posts/{post_id}/").json()
    assert post["status"] == "failed"
    assert post["status_reason"] == "The image service is down."
    last_step = post["steps"][-1]
    assert last_step["stage"] == "imaging"
    assert last_step["succeeded"] is False
    assert Notification.objects.filter(kind="post_failed").exists()


def test_running_a_waiting_post_again_does_nothing(plan):
    post = Post.objects.create(user=plan.user, plan=plan, status="awaiting_approval")

    assert run_stage(post.id) == "awaiting_approval"
    assert not post.steps.exists()


def test_a_bug_in_a_stage_fails_the_post_instead_of_leaving_it_stuck(plan, monkeypatch):
    def crash(artwork_bytes, headline, source_line):
        raise RuntimeError("A bug in the poster code.")

    monkeypatch.setattr("studio.pipeline.render_poster", crash)
    post = Post.objects.create(user=plan.user, plan=plan, topic=plan.topics.first())

    with pytest.raises(RuntimeError):
        advance_post_task.delay(str(post.id))

    post.refresh_from_db()
    assert post.status == "failed"
    assert "unexpected error" in post.status_reason
    assert Notification.objects.filter(kind="post_failed").exists()


def test_a_bug_after_a_post_finished_does_not_change_it(plan):
    post = Post.objects.create(user=plan.user, plan=plan, status="published")

    assert fail_after_crash(post.id) is False
    post.refresh_from_db()
    assert post.status == "published"
