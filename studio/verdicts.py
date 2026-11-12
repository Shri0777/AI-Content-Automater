"""Turn an AI review into a verdict with fixed, readable rules.

The AI gives scores and lists issues, but it does not decide the verdict.
These rules do, so the same review always gets the same verdict.
"""

# Every score (1 to 5) must be at least this for a "pass".
PASS_SCORE = 4


def decide_verdict(scores, issues):
    """Return "pass", "revise" or "reject" for a review.

    - Any blocker issue means "reject".
    - Otherwise every score must reach PASS_SCORE for a "pass".
    - Anything else means "revise".
    """
    for issue in issues:
        if issue["severity"] == "blocker":
            return "reject"
    if not scores:
        return "revise"
    if min(scores.values()) >= PASS_SCORE:
        return "pass"
    return "revise"
