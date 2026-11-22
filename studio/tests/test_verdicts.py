"""Every combination of scores and issues gets the verdict the rules promise.

The expected verdict is worked out here in a second, separate way (counting
low scores), so a mistake in decide_verdict() cannot hide in the test.
"""

import pytest

from studio.verdicts import SCORE_NAMES, decide_verdict, total_score

ISSUE_CASES = {
    "no issues": [],
    "a minor issue": [{"severity": "minor", "problem": "p", "fix_instruction": ""}],
    "a blocker": [{"severity": "blocker", "problem": "p", "fix_instruction": ""}],
    # Only our own checks raise major issues (a slide with too many words).
    "a major issue": [{"severity": "major", "problem": "p", "fix_instruction": ""}],
}


def every_score_combination():
    """Return all 15625 ways to give the six scores a value from 1 to 5."""
    combinations = [{}]
    for name in SCORE_NAMES:
        longer = []
        for partial in combinations:
            for value in range(1, 6):
                scores = dict(partial)
                scores[name] = value
                longer.append(scores)
        combinations = longer
    return combinations


def expected_verdict(scores, issue_case, strict):
    """Work out the promised verdict without calling decide_verdict()."""
    if issue_case == "a blocker":
        return "reject"
    if issue_case == "a major issue":
        return "revise"
    low_scores = [value for value in scores.values() if value < 4]
    if low_scores:
        return "revise"
    if strict and (scores["grounding"] != 5 or scores["safety"] != 5):
        return "revise"
    return "pass"


@pytest.mark.parametrize("issue_case", list(ISSUE_CASES))
@pytest.mark.parametrize("strict", [False, True])
def test_every_score_combination_gets_the_promised_verdict(issue_case, strict):
    combinations = every_score_combination()
    assert len(combinations) == 15625

    for scores in combinations:
        verdict = decide_verdict(scores, ISSUE_CASES[issue_case], strict=strict)
        assert verdict == expected_verdict(scores, issue_case, strict), scores


def test_a_review_missing_a_score_is_never_a_pass():
    for name in SCORE_NAMES:
        scores = {other: 5 for other in SCORE_NAMES if other != name}

        assert decide_verdict(scores, []) == "revise"


def test_the_total_score_adds_up_the_six_scores():
    assert total_score({name: 3 for name in SCORE_NAMES}) == 18
    assert total_score({name: 5 for name in SCORE_NAMES}) == 30
    assert total_score({}) == 0


def test_shareability_is_one_of_the_scores_a_pass_needs():
    scores = {name: 5 for name in SCORE_NAMES}
    scores["shareability"] = 3

    assert decide_verdict(scores, []) == "revise"
