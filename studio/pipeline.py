"""The stages that turn a new post into one waiting for approval.

    researching -> drafting -> imaging -> reviewing -> awaiting_approval

Each stage function does its work, saves it, then moves the post to the
next status. A stage first checks whether its work is already saved, so
running it twice (for example after a crash) never makes things twice.

Each stage returns the list of AI models it used, so studio/runner.py can
record which provider, prompt versions and tokens went into the post.
"""

from credentials.services import require_credential
from newsroom.services import pick_article, record_article_use
from notifications.services import notify
from studio.files import save_poster
from studio.models import PostVersion, Review
from studio.posters import render_poster
from studio.providers import get_image_model, get_text_model
from studio.statuses import change_status
from studio.verdicts import decide_verdict

POSTER_WIDTH = 1080
POSTER_HEIGHT = 1080
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
        source_line = f"Source: {post.article.source_name}"
        poster = render_poster(
            artwork, version.headline, source_line, POSTER_WIDTH, POSTER_HEIGHT
        )
        version.image_prompt = prompt
        version.poster_path = save_poster(version, poster)
        version.save(update_fields=["image_prompt", "poster_path"])
    change_status(post, "reviewing")
    return used


def review(post):
    """Have the text model check the post, then ask the user to approve it."""
    used = []
    version = post.latest_version()
    if not Review.objects.filter(version=version).exists():
        text_model = text_model_for(post)
        used.append(text_model)
        result = text_model.review_post(post.article, version.headline, version.caption)
        Review.objects.create(
            version=version,
            scores=result["scores"],
            issues=result["issues"],
            verdict=decide_verdict(result["scores"], result["issues"]),
        )
    change_status(post, "awaiting_approval")
    message = f"A new post for '{post.plan.name}' is ready for your review."
    notify(post.user, "post_awaiting_approval", message, related=post)
    return used


STAGES = {
    "researching": research,
    "drafting": draft,
    "imaging": make_poster,
    "reviewing": review,
}
