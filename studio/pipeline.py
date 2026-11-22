"""The stages that turn a new post into one waiting for approval.

    researching -> drafting -> imaging -> reviewing -> awaiting_approval
                                            ^   |
                                            |   v
                                          correcting (at most 2 rounds)

"imaging" draws the slides (studio/visuals.py). It calls an image model only
when the plan asks for AI artwork; by default the slides are plain type.

Each stage function does its work, saves it, then moves the post to the
next status. A stage first checks whether its work is already saved, so
running it twice (for example after a crash) never makes things twice.

Each stage returns the list of AI models it used, so studio/runner.py can
record which provider, prompt versions and tokens went into the post.
"""

from django.utils import timezone

from credentials.services import require_credential
from newsroom.services import pick_article, record_article_use
from notifications.services import notify
from planning.custom_topics import requirements_for
from publishing.gate import check_auto_post
from publishing.tasks import publish_post_task
from studio.files import save_artwork
from studio.models import PostVersion, Review
from studio.posters import fit_artwork
from studio.providers import get_image_model, get_text_model
from studio.reviewing import save_review, should_correct
from studio.statuses import change_status
from studio.visuals import artwork_of, save_visuals

# The AI artwork is asked for square; each slide crops what it needs.
ARTWORK_SIZE = 1080
NO_ARTICLE_REASON = (
    "No article was good enough for this topic (fresh, unused, with enough "
    "text, and rated relevant and credible), so nothing was made rather "
    "than posting filler."
)


# Demo mode offers only the fictional demo articles; a real AI model rightly
# rates them not credible, so with real keys every post would be skipped.
DEMO_NEWS_WITH_REAL_MODEL = (
    " This server is in demo mode, so it only offers fictional demo articles, "
    "and your real AI model does not rate them credible. To use real news, "
    "set DEMO_MODE=false and restart the app."
)


def skip_reason(post, text_model):
    """Return why the post was skipped, explaining demo news to real models."""
    if post.demo_mode and text_model.credential.adapter != "demo":
        return NO_ARTICLE_REASON + DEMO_NEWS_WITH_REAL_MODEL
    return NO_ARTICLE_REASON


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
            reason = skip_reason(post, text_model)
            change_status(post, "skipped", reason)
            notify(post.user, "post_skipped", reason, related=post)
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
        written = text_model.write_post(
            post.article, requirements_for(post.plan, post.topic)
        )
        PostVersion.objects.create(
            post=post,
            number=1,
            headline=written["headline"],
            points=written.get("points", []),
            figure=written.get("figure", {}),
            quote=written.get("quote", {}),
            takeaway=written.get("takeaway", ""),
            caption=written["caption"],
        )
    change_status(post, "imaging")
    return used


def make_poster(post):
    """Draw the slides, with AI artwork on the cover only if the plan asks."""
    used = []
    version = post.latest_version()
    if not version.poster_path:
        artwork = artwork_of(version)
        if post.plan.ai_artwork_enabled and not artwork:
            used, artwork = make_artwork(post, version)
        save_visuals(post, version, artwork)
    change_status(post, "reviewing")
    return used


def make_artwork(post, version):
    """Make and save AI artwork for the cover; return (models used, PNG bytes)."""
    text_model = text_model_for(post)
    image_model = get_image_model(require_credential(post.user, "image"))
    prompt = text_model.write_image_prompt(post.article, version.headline)
    made = image_model.make_artwork(prompt, ARTWORK_SIZE, ARTWORK_SIZE)
    artwork = fit_artwork(made, ARTWORK_SIZE, ARTWORK_SIZE)
    version.image_prompt = prompt
    version.artwork_path = save_artwork(version, artwork)
    version.save(update_fields=["image_prompt", "artwork_path"])
    return [text_model, image_model], artwork


def review(post):
    """Have the text model check the post; correct it or hand it to the user."""
    used = []
    version = post.latest_version()
    found = Review.objects.filter(version=version).first()
    if found is None:
        text_model = text_model_for(post)
        used.append(text_model)
        result = text_model.review_post(post.article, version)
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
    """Write the next version following the review's notes, on the same artwork.

    No new image is made: the slides are drawn again with the new words.
    """
    used = []
    version = post.latest_version()
    found = Review.objects.filter(version=version).first()
    if found is not None:
        text_model = text_model_for(post)
        used.append(text_model)
        fixed = text_model.correct_post(
            post.article, requirements_for(post.plan, post.topic), version, found.issues
        )
        new_version = PostVersion.objects.create(
            post=post,
            number=version.number + 1,
            headline=fixed["headline"],
            points=fixed.get("points", version.points),
            figure=fixed.get("figure", {}),
            quote=fixed.get("quote", {}),
            takeaway=fixed.get("takeaway", ""),
            caption=fixed["caption"],
            image_prompt=version.image_prompt,
            artwork_path=version.artwork_path,
        )
        save_visuals(post, new_version, artwork_of(version))
    change_status(post, "reviewing")
    return used


STAGES = {
    "researching": research,
    "drafting": draft,
    "imaging": make_poster,
    "reviewing": review,
    "correcting": correct,
}
