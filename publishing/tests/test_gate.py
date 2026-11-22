"""The auto-post gate, as a table: one row per case, read left to right.

Columns: approval mode | review verdict | review issues | total score |
topic | every score 5? | gate opens?

The plan's minimum score is 26 of 30 (the default). "strict" topics are layoffs,
hiring and Linux tips; "normal" is AI news.
"""

import pytest

from publishing.gate import check_auto_post
from studio.verdicts import SCORE_NAMES

GATE_TABLE = [
    # mode,    verdict,   issues,  total, topic,    all 5s, opens
    ("manual", "pass", "none", 30, "normal", True, False),
    ("manual", "pass", "none", 30, "strict", True, False),
    ("auto", "revise", "none", 30, "normal", True, False),
    ("auto", "reject", "none", 30, "normal", True, False),
    ("auto", "pass", "minor", 30, "normal", True, False),
    ("auto", "pass", "none", 25, "normal", False, False),
    ("auto", "pass", "none", 26, "normal", False, True),
    ("auto", "pass", "none", 30, "normal", True, True),
    ("auto", "pass", "none", 29, "strict", False, False),
    ("auto", "pass", "none", 30, "strict", True, True),
    ("auto", "pass", "minor", 30, "strict", True, False),
    ("auto", "revise", "none", 30, "strict", True, False),
]

TOPICS = {"normal": "ai_news", "strict": "layoffs"}


class Plan:
    """Just the plan settings the gate reads."""

    def __init__(self, mode):
        self.approval_mode = mode
        self.auto_post_min_score = 26


class Topic:
    """Just the topic setting the gate reads."""

    def __init__(self, kind):
        self.preset = TOPICS[kind]


class Review:
    """Just the review details the gate reads."""

    def __init__(self, verdict, issues, total, all_fives):
        self.verdict = verdict
        self.issues = []
        if issues == "minor":
            self.issues = [{"severity": "minor", "problem": "p", "fix_instruction": ""}]
        self.scores = scores_adding_up_to(total, all_fives)

    def total(self):
        return sum(self.scores.values())


def scores_adding_up_to(total, all_fives):
    """Return six scores (each 1 to 5) that add up to total."""
    if all_fives:
        assert total == 30
        return {name: 5 for name in SCORE_NAMES}
    scores = {name: 4 for name in SCORE_NAMES}
    extra = max(0, total - 24)
    for name in SCORE_NAMES[:extra]:
        scores[name] = 5
    scores["safety"] = scores["safety"] - max(0, 24 - total)
    return scores


@pytest.mark.parametrize("row", GATE_TABLE)
def test_the_gate_follows_its_table(row):
    mode, verdict, issues, total, topic, all_fives, opens = row
    review = Review(verdict, issues, total, all_fives)
    assert review.total() == total

    allowed, why_not = check_auto_post(Plan(mode), Topic(topic), review)

    assert allowed is opens
    assert (why_not == "") is opens


def test_a_post_without_a_review_never_goes_out_on_its_own():
    allowed, why_not = check_auto_post(Plan("auto"), Topic("normal"), None)

    assert allowed is False
    assert "no review" in why_not


@pytest.mark.parametrize("topic", list(TOPICS))
def test_the_gate_is_closed_for_every_combination_but_a_clean_pass(topic):
    opened = []
    for mode in ["manual", "auto"]:
        for verdict in ["pass", "revise", "reject"]:
            for issues in ["none", "minor"]:
                for total, all_fives in [
                    (22, False),
                    (25, False),
                    (26, False),
                    (30, True),
                ]:
                    review = Review(verdict, issues, total, all_fives)
                    assert review.total() == total
                    allowed, _ = check_auto_post(Plan(mode), Topic(topic), review)
                    if allowed:
                        opened.append((mode, verdict, issues, total))

    expected = [("auto", "pass", "none", 30)]
    if topic == "normal":
        expected = [("auto", "pass", "none", 26), ("auto", "pass", "none", 30)]
    assert opened == expected
