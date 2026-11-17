"""Choose an article for a post, preview a topic, and remember what was used.

Articles come from the shared store, which newsroom/ingest.py fills. If a
topic's sources were not read in the last 30 minutes, they are read first.
When a source is over its daily budget or down, the plan simply uses the
articles already stored.
"""

from django.utils import timezone

from core.errors import AppError
from newsroom.ingest import ensure_recent_ingest
from newsroom.models import ArticleUse
from newsroom.presets import TOPIC_PRESETS
from newsroom.ranking import best_rated, make_shortlist
from quotas.services import use_daily_quota


class UnknownPreset(AppError):
    """Raised for a topic preset that does not exist."""

    status = 400
    code = "unknown_preset"
    title = "Unknown topic"


def pick_article(plan, topic, text_model):
    """Return the best article for the topic that passes every gate, or None.

    text_model is the plan owner's own model; it rates the shortlist.
    """
    ensure_recent_ingest(topic.preset)
    shortlist = make_shortlist(plan, topic.preset, topic.name, timezone.now())
    if not shortlist:
        return None
    ratings = text_model.score_articles(shortlist, plan.requirements)
    return best_rated(shortlist, ratings)


def record_article_use(plan, article):
    """Remember that plan used article, so it is not picked again."""
    ArticleUse.objects.get_or_create(plan=plan, article=article)


def preview_topic(user, preset):
    """Return the best articles stored for a preset right now (no AI rating).

    Counts towards the user's daily news-preview limit.
    """
    if preset not in TOPIC_PRESETS:
        raise UnknownPreset(f"'{preset}' is not a topic preset.")
    use_daily_quota(user, "news_previews_per_day")
    ensure_recent_ingest(preset)
    label = TOPIC_PRESETS[preset]["label"]
    return make_shortlist(None, preset, label, timezone.now())
