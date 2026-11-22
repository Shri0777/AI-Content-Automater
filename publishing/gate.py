"""The auto-post gate: may a reviewed post go out without asking the user?

This is the only place that decides it, and it is closed by default: every
rule below can only keep the gate shut. A post goes out on its own only when
ALL of these hold:

1. The plan's approval mode is "auto".
2. The post has a review, and its verdict is "pass" (studio/verdicts.py).
3. The review noted no issues at all, not even minor ones.
4. The review's total score (6 to 30) reaches the plan's auto_post_min_score.
5. On a strict topic (layoffs, hiring, Linux tips) every score is 5.

These rules encode how much editorial risk the owner accepts. They are
tested as one row per case in publishing/tests/test_gate.py; change the
thresholds there and here together.
"""

from newsroom.presets import get_preset
from studio.verdicts import SCORE_NAMES


def is_strict_topic(topic):
    """Return True if the topic's preset asks for the strict review."""
    if topic is None:
        return False
    return (get_preset(topic.preset) or {}).get("strict_review", False)


def mode_problem(plan, topic, review):
    """Rule 1: only "auto" plans post on their own."""
    if plan.approval_mode != "auto":
        return "This plan asks you to approve every post."
    return ""


def verdict_problem(plan, topic, review):
    """Rule 2: the post needs a review that passed."""
    if review is None:
        return "The post has no review yet."
    if review.verdict != "pass":
        return f"The review did not pass it (verdict: {review.verdict})."
    return ""


def issues_problem(plan, topic, review):
    """Rule 3: the review noted nothing at all."""
    if review.issues:
        return "The review noted issues, so a person should look first."
    return ""


def score_problem(plan, topic, review):
    """Rule 4: the total score reaches the plan's minimum."""
    if review.total() < plan.auto_post_min_score:
        return (
            f"Its review score ({review.total()} of 30) is below this plan's "
            f"minimum for automatic posting ({plan.auto_post_min_score})."
        )
    return ""


def strict_topic_problem(plan, topic, review):
    """Rule 5: on a strict topic, every score is 5."""
    if not is_strict_topic(topic):
        return ""
    for name in SCORE_NAMES:
        if review.scores.get(name) != 5:
            return "On this topic, posts only go out on their own when perfect."
    return ""


# Checked in this order; the first problem found keeps the gate closed.
RULES = [
    mode_problem,
    verdict_problem,
    issues_problem,
    score_problem,
    strict_topic_problem,
]


def check_auto_post(plan, topic, review):
    """Return (True, "") if the post may go out on its own, else (False, why)."""
    for rule in RULES:
        problem = rule(plan, topic, review)
        if problem:
            return False, problem
    return True, ""
