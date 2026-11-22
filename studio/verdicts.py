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
# shareability: would a busy professional send this to a colleague because
# it tells them something specific and useful? Sends, shares and replies are
# what every platform rewards most.
SCORE_NAMES = ["grounding", "relevance", "clarity", "tone", "safety", "shareability"]


def has_severity(issues, severity):
    """Return True if any issue has the given severity."""
    for issue in issues:
        if issue["severity"] == severity:
            return True
    return False


def has_blocker(issues):
    """Return True if any issue is a blocker."""
    return has_severity(issues, "blocker")


def decide_verdict(scores, issues, strict=False):
    """Return "pass", "revise" or "reject" for a review.

    - Any blocker issue means "reject".
    - Any major issue means "revise". Only our own checks raise these (for
      example a slide with too many words, studio/post_content.py); the AI
      reviewer can only say "minor" or "blocker".
    - A missing score means "revise".
    - Every score must reach PASS_SCORE for a "pass", and on strict topics
      the STRICT_SCORES must be 5.
    - Anything else means "revise".
    """
    if has_blocker(issues):
        return "reject"
    if has_severity(issues, "major") or not scores_pass(scores, strict):
        return "revise"
    return "pass"


def scores_pass(scores, strict):
    """Return True if every score reaches PASS_SCORE (and 5 where strict)."""
    for name in SCORE_NAMES:
        if name not in scores or scores[name] < PASS_SCORE:
            return False
    if strict:
        for name in STRICT_SCORES:
            if scores[name] < 5:
                return False
    return True


def total_score(scores):
    """Return the sum of the six scores (6 to 30), for comparing versions."""
    total = 0
    for name in SCORE_NAMES:
        total = total + scores.get(name, 0)
    return total
