"""The stages that turn a new post into one waiting for approval.

    researching -> drafting -> imaging -> reviewing -> awaiting_approval

Each stage function does its work, saves it, then moves the post to the
next status. A stage first checks whether its work is already saved, so
running it twice (for example after a crash) never makes things twice.
studio/tasks.py runs one stage at a time with run_stage().
"""

import time

from core.errors import ProviderError
from credentials.services import CredentialMissing, require_credential
from newsroom.services import pick_article, record_article_use
from notifications.services import notify
from studio.files import save_poster
from studio.models import GenerationStep, Post, PostVersion, Review
from studio.posters import render_poster
from studio.providers import get_image_model, get_text_model
from studio.statuses import change_status
from studio.verdicts import decide_verdict

POSTER_WIDTH = 1080
POSTER_HEIGHT = 1080
NO_ARTICLE_REASON = (
    "No fresh, unused article was found for this topic, "
    "so nothing was made rather than posting filler."
)


def text_model_for(post):
    """Return the text model from the post owner's saved credential."""
    return get_text_model(require_credential(post.user, "text"))


def research(post):
    """Choose an article for the post, or skip the post if none is good."""
    if post.article is None:
        article = pick_article(post.plan, post.topic.preset)
        if article is None:
            change_status(post, "skipped", NO_ARTICLE_REASON)
            notify(post.user, "post_skipped", NO_ARTICLE_REASON, related=post)
            return
        record_article_use(post.plan, article)
        post.article = article
        post.save(update_fields=["article"])
    change_status(post, "drafting")


def draft(post):
    """Write the headline and caption as version 1 of the post."""
    if post.latest_version() is None:
        written = text_model_for(post).write_post(post.article, post.plan.requirements)
        PostVersion.objects.create(
            post=post,
            number=1,
            headline=written["headline"],
            caption=written["caption"],
        )
    change_status(post, "imaging")


def make_poster(post):
    """Write an image prompt, make the artwork and put the headline on it."""
    version = post.latest_version()
    if not version.poster_path:
        image_model = get_image_model(require_credential(post.user, "image"))
        prompt = text_model_for(post).write_image_prompt(post.article, version.headline)
        artwork = image_model.make_artwork(prompt, POSTER_WIDTH, POSTER_HEIGHT)
        source_line = f"Source: {post.article.source_name}"
        poster = render_poster(artwork, version.headline, source_line)
        version.image_prompt = prompt
        version.poster_path = save_poster(version, poster)
        version.save(update_fields=["image_prompt", "poster_path"])
    change_status(post, "reviewing")


def review(post):
    """Have the text model check the post, then ask the user to approve it."""
    version = post.latest_version()
    if not Review.objects.filter(version=version).exists():
        result = text_model_for(post).review_post(
            post.article, version.headline, version.caption
        )
        verdict = decide_verdict(result["scores"], result["issues"])
        Review.objects.create(
            version=version,
            scores=result["scores"],
            issues=result["issues"],
            verdict=verdict,
        )
    change_status(post, "awaiting_approval")
    message = f"A new post for '{post.plan.name}' is ready for your review."
    notify(post.user, "post_awaiting_approval", message, related=post)


STAGES = {
    "researching": research,
    "drafting": draft,
    "imaging": make_poster,
    "reviewing": review,
}


def record_step(post, stage_name, started, error=""):
    """Save a GenerationStep row for one stage run."""
    GenerationStep.objects.create(
        post=post,
        stage=stage_name,
        succeeded=error == "",
        duration_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


def run_stage(post_id):
    """Run the stage for the post's current status and return its new status.

    A post that is waiting for the user, or finished, is left alone. A post
    deleted (with its plan) while its job waited returns "deleted".
    """
    post = (
        Post.objects.select_related("plan", "topic", "article", "user")
        .filter(id=post_id)
        .first()
    )
    if post is None:
        return "deleted"
    stage_name = post.status
    stage = STAGES.get(stage_name)
    if stage is None:
        return post.status
    started = time.monotonic()
    try:
        stage(post)
    except (ProviderError, CredentialMissing) as error:
        record_step(post, stage_name, started, error=str(error))
        change_status(post, "failed", str(error))
        notify(post.user, "post_failed", str(error), related=post)
        return post.status
    record_step(post, stage_name, started)
    return post.status
