"""Save the AI review of a version, with our own checks added, and decide
whether the post gets another correction round (studio/pipeline.py).
"""

from newsroom.presets import get_preset
from studio.guards import LEAK_ISSUE, leaked_instructions
from studio.models import Review
from studio.post_content import layout_issues
from studio.verdicts import decide_verdict

# A post is corrected at most this many times (so at most 3 versions).
MAX_CORRECTION_ROUNDS = 2


def is_strict(post):
    """Return True if the post's topic needs the stricter review rules."""
    if post.topic is None:
        return False
    return (get_preset(post.topic.preset) or {}).get("strict_review", False)


def written_text(version):
    """Return every word of a version that people will read, as one text."""
    figure = version.figure or {}
    quote = version.quote or {}
    parts = [version.headline, *version.points, version.caption, version.takeaway]
    parts = parts + [figure.get("label", ""), quote.get("text", "")]
    return " ".join(parts)


def save_review(post, version, result):
    """Save the model's review, adding our own checks' issues to it.

    A slide with too many words is a "major" issue (a rewrite); a post that
    leaked our prompts gets a blocker.
    """
    issues = result["issues"] + layout_issues(version)
    if leaked_instructions(written_text(version)):
        issues = issues + [LEAK_ISSUE]
    return Review.objects.create(
        version=version,
        scores=result["scores"],
        issues=issues,
        verdict=decide_verdict(result["scores"], issues, strict=is_strict(post)),
    )


def should_correct(version, review):
    """Return True if the post gets another correction round.

    Not after a pass, not after MAX_CORRECTION_ROUNDS, and not when the last
    correction did not raise the total score (it is not getting better).
    """
    if review.verdict == "pass" or version.number > MAX_CORRECTION_ROUNDS:
        return False
    if version.number == 1:
        return True
    previous = Review.objects.filter(
        version__post=version.post, version__number=version.number - 1
    ).first()
    return previous is None or review.total() > previous.total()
