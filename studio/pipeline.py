"""The stages that turn a new post into one waiting for approval.

    researching -> drafting -> imaging -> reviewing -> awaiting_approval
                                            ^   |
                                            |   v
                                          correcting (at most 2 rounds)

Each stage function does its work, saves it, then moves the post to the
next status. A stage first checks whether its work is already saved, so
running it twice (for example after a crash) never makes things twice.

Each stage returns the list of AI models it used, so studio/runner.py can
record which provider, prompt versions and tokens went into the post.
"""

from django.utils import timezone

from credentials.services import require_credential
from newsroom.presets import TOPIC_PRESETS
from newsroom.services import pick_article, record_article_use
from notifications.services import notify
from publishing.gate import check_auto_post
from publishing.tasks import publish_post_task
from studio.files import read_artwork, save_artwork, save_poster
from studio.guards import LEAK_ISSUE, leaked_instructions
from studio.models import PostVersion, Review
from studio.posters import fit_artwork, render_poster
from studio.providers import get_image_model, get_text_model
from studio.statuses import change_status
from studio.verdicts import decide_verdict

POSTER_WIDTH = 1080
POSTER_HEIGHT = 1080
# A post is corrected at most this many times (so at most 3 versions).
MAX_CORRECTION_ROUNDS = 2
NO_ARTICLE_REASON = (
    "No article was good enough for this topic (fresh, unused, with enough "
    "text, and rated relevant and credible), so nothing was made rather "
    "than posting filler."
)


def text_model_for(post):
    """Return the text model from the post owner's saved credential."""
    return get_text_model(require_credential(post.user, "text"))


def research(post):
    """Choose an article for the post, or skip the post if none is good.

    The owner's text model rates the shortlist (newsroom/ranking.py).
    """
    used = []
    if post.article is None:
        text_model = text_model_for(post)
        used.append(text_model)
        article = pick_article(post.plan, post.topic, text_model)
        if article is None:
            change_status(post, "skipped", NO_ARTICLE_REASON)
            notify(post.user, "post_skipped", NO_ARTICLE_REASON, related=post)
            return used
        record_article_use(post.plan, article)
        post.article = article
        post.save(update_fields=["article"])
    change_status(post, "drafting")
    return used


def draft(post):
    """Write the headline and caption as version 1 of the post."""
    used = []
    if post.latest_version() is None:
        text_model = text_model_for(post)
        used.append(text_model)
        written = text_model.write_post(post.article, post.plan.requirements)
        PostVersion.objects.create(
            post=post,
            number=1,
            headline=written["headline"],
            caption=written["caption"],
        )
    change_status(post, "imaging")
    return used


def make_poster(post):
    """Write an image prompt, make the artwork and put the headline on it."""
    used = []
    version = post.latest_version()
    if not version.poster_path:
        text_model = text_model_for(post)
        image_model = get_image_model(require_credential(post.user, "image"))
        used = [text_model, image_model]
        prompt = text_model.write_image_prompt(post.article, version.headline)
        artwork = image_model.make_artwork(prompt, POSTER_WIDTH, POSTER_HEIGHT)
        version.image_prompt = prompt
        version.artwork_path = save_artwork(
            version, fit_artwork(artwork, POSTER_WIDTH, POSTER_HEIGHT)
        )
        version.poster_path = save_poster(version, poster_for(post, version, artwork))
        version.save(update_fields=["image_prompt", "artwork_path", "poster_path"])
    change_status(post, "reviewing")
    return used


def poster_for(post, version, artwork):
    """Return the poster PNG: version's headline and the source on artwork."""
    source_line = f"Source: {post.article.source_name}"
    return render_poster(
        artwork, version.headline, source_line, POSTER_WIDTH, POSTER_HEIGHT
    )


def is_strict(post):
    """Return True if the post's topic needs the stricter review rules."""
    if post.topic is None:
        return False
    return TOPIC_PRESETS[post.topic.preset].get("strict_review", False)


def save_review(post, version, result):
    """Save the model's review, adding a blocker if the post leaked our prompts."""
    issues = result["issues"]
    if leaked_instructions(f"{version.headline} {version.caption}"):
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


def review(post):
    """Have the text model check the post; correct it or hand it to the user."""
    used = []
    version = post.latest_version()
    found = Review.objects.filter(version=version).first()
    if found is None:
        text_model = text_model_for(post)
        used.append(text_model)
        result = text_model.review_post(post.article, version.headline, version.caption)
        found = save_review(post, version, result)
    if should_correct(version, found):
        change_status(post, "correcting")
        return used
    hand_over(post)
    return used


def hand_over(post):
    """Post it automatically if the auto-post gate allows, else ask the user."""
    final = post.final_version()
    final_review = Review.objects.filter(version=final).first()
    allowed, why_not = check_auto_post(post.plan, post.topic, final_review)
    if allowed:
        change_status(post, "approved", "Approved automatically: the review was clean.")
        if post.slot is None or post.slot.publish_at <= timezone.now():
            publish_post_task.delay(str(post.id))
        return
    change_status(post, "awaiting_approval")
    message = f"A new post for '{post.plan.name}' is ready for your review."
    if post.plan.approval_mode == "auto":
        message = f"A post for '{post.plan.name}' needs your approval: {why_not}"
    notify(post.user, "post_awaiting_approval", message, related=post)


def correct(post):
    """Write the next version following the review's notes, on the same artwork."""
    used = []
    version = post.latest_version()
    found = Review.objects.filter(version=version).first()
    if found is not None:
        text_model = text_model_for(post)
        used.append(text_model)
        fixed = text_model.correct_post(
            post.article, post.plan.requirements, version, found.issues
        )
        new_version = PostVersion.objects.create(
            post=post,
            number=version.number + 1,
            headline=fixed["headline"],
            caption=fixed["caption"],
            image_prompt=version.image_prompt,
            artwork_path=version.artwork_path,
        )
        artwork = read_artwork(version)
        new_version.poster_path = save_poster(
            new_version, poster_for(post, new_version, artwork)
        )
        new_version.save(update_fields=["poster_path"])
    change_status(post, "reviewing")
    return used


STAGES = {
    "researching": research,
    "drafting": draft,
    "imaging": make_poster,
    "reviewing": review,
    "correcting": correct,
}
