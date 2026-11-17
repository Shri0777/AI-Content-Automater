"""The review-and-correct loop: at most 2 rounds, only while it improves."""

import pytest

from demo.image_model import DemoImageModel
from demo.text_model import DemoTextModel
from studio.models import GenerationStep, Post, Review
from studio.runner import run_stage

PERFECT = {"grounding": 5, "relevance": 5, "clarity": 5, "tone": 5, "safety": 5}


def scores_with(clarity, grounding=5):
    """Return review scores with one weak spot to correct."""
    scores = dict(PERFECT)
    scores["clarity"] = clarity
    scores["grounding"] = grounding
    return scores


@pytest.fixture
def scripted_reviews(monkeypatch):
    """Make the demo reviewer answer with the next scores from a list."""
    queue = []

    def next_review(self, article, headline, caption):
        scores = queue.pop(0)
        issues = []
        if min(scores.values()) < 4:
            issues.append(
                {
                    "severity": "minor",
                    "problem": "Unclear.",
                    "fix_instruction": "Clarify.",
                }
            )
        return {"scores": scores, "issues": issues}

    monkeypatch.setattr(DemoTextModel, "review_post", next_review)
    return queue


def make_post(plan):
    """Run a new post through every stage until it waits for the user."""
    post = Post.objects.create(
        user=plan.user, plan=plan, topic=plan.topics.first(), demo_mode=True
    )
    for _ in range(12):
        status = run_stage(post.id)
        if status not in [
            "researching",
            "drafting",
            "imaging",
            "reviewing",
            "correcting",
        ]:
            break
    post.refresh_from_db()
    return post


def test_a_post_that_passes_first_time_is_not_corrected(plan, scripted_reviews):
    scripted_reviews.extend([PERFECT])

    post = make_post(plan)

    assert post.status == "awaiting_approval"
    assert post.versions.count() == 1


def test_a_weak_post_is_corrected_until_it_passes(plan, scripted_reviews, monkeypatch):
    drawings = []
    real_draw = DemoImageModel.draw

    def count_drawings(self, prompt, width, height):
        drawings.append(prompt)
        return real_draw(self, prompt, width, height)

    monkeypatch.setattr(DemoImageModel, "draw", count_drawings)
    scripted_reviews.extend([scores_with(clarity=2), PERFECT])

    post = make_post(plan)

    assert post.status == "awaiting_approval"
    first, second = post.versions.order_by("number")
    assert post.final_version() == second
    # The correction reuses the artwork: only one image was ever made.
    assert len(drawings) == 1
    assert second.artwork_path == first.artwork_path
    assert second.poster_path != first.poster_path
    assert GenerationStep.objects.filter(post=post, stage="correcting").count() == 1


def test_there_are_at_most_two_correction_rounds(plan, scripted_reviews):
    scripted_reviews.extend(
        [scores_with(clarity=1), scores_with(clarity=2), scores_with(clarity=3)]
    )

    post = make_post(plan)

    assert post.status == "awaiting_approval"
    assert post.versions.count() == 3
    assert Review.objects.filter(version__post=post).count() == 3


def test_correcting_stops_when_the_score_does_not_improve(plan, scripted_reviews):
    scripted_reviews.extend([scores_with(clarity=3), scores_with(clarity=2)])

    post = make_post(plan)

    assert post.status == "awaiting_approval"
    assert post.versions.count() == 2
    # The correction came out worse, so the first version is shown and used.
    assert post.final_version().number == 1


def test_a_strict_topic_needs_perfect_grounding_to_pass(plan, scripted_reviews):
    plan.topics.update(preset="linux_tips")
    almost = scores_with(clarity=5, grounding=4)
    scripted_reviews.extend([almost, PERFECT])

    post = make_post(plan)

    assert post.versions.count() == 2
    first_review = Review.objects.get(version__post=post, version__number=1)
    assert first_review.verdict == "revise"


def test_the_same_scores_pass_on_a_normal_topic(plan, scripted_reviews):
    scripted_reviews.extend([scores_with(clarity=5, grounding=4)])

    post = make_post(plan)

    assert post.versions.count() == 1
    assert Review.objects.get(version__post=post).verdict == "pass"
