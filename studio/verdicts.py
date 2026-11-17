"""Turn an AI review into a verdict with fixed, readable rules.

The AI gives scores and lists issues, but it does not decide the verdict.
These rules do, so the same review always gets the same verdict.
"""

# Every score (1 to 5) must be at least this for a "pass".
PASS_SCORE = 4
# Strict topics name real companies and people (layoffs, hiring) or give
# commands that people run on their own computers (Linux tips). For those,
# these scores must be perfect for a "pass".
STRICT_SCORES = ["grounding", "safety"]
SCORE_NAMES = ["grounding", "relevance", "clarity", "tone", "safety"]


def has_blocker(issues):
    """Return True if any issue is a blocker."""
    for issue in issues:
        if issue["severity"] == "blocker":
            return True
    return False


def decide_verdict(scores, issues, strict=False):
    """Return "pass", "revise" or "reject" for a review.

    - Any blocker issue means "reject".
    - A missing score means "revise".
    - Every score must reach PASS_SCORE for a "pass", and on strict topics
      the STRICT_SCORES must be 5.
    - Anything else means "revise".
    """
    if has_blocker(issues):
        return "reject"
    for name in SCORE_NAMES:
        if name not in scores or scores[name] < PASS_SCORE:
            return "revise"
    if strict:
        for name in STRICT_SCORES:
            if scores[name] < 5:
                return "revise"
    return "pass"


def total_score(scores):
    """Return the sum of the five scores (5 to 25), for comparing versions."""
    total = 0
    for name in SCORE_NAMES:
        total = total + scores.get(name, 0)
    return total
