"""Choose the best article for a plan: quality gates, then ranking.

The gates, in order (design/system-design.md §7.2):
1. Source policy: only the preset's own sources are read at all, and each
   source has a tier (primary, reputable, aggregator).
2. Freshness: news topics only use articles inside the preset's window.
3. Not used by this plan before (the ArticleUse ledger).
4. Enough text: at least MIN_TEXT_CHARACTERS, so the post can be accurate.
5. A cheap score (tier, recency, length, topic words, popularity) picks a
   shortlist, without two copies of the same story.
6. The user's own text model rates the shortlist in one request. Only an
   article rated relevant, credible and verifiable can be chosen.

If nothing passes, None is returned and the post is skipped: never filler.
"""

from datetime import timedelta
from difflib import SequenceMatcher

from django.conf import settings

from newsroom.ingest import MIN_TEXT_CHARACTERS
from newsroom.models import Article, ArticleUse
from newsroom.presets import TOPIC_PRESETS

SHORTLIST_SIZE = 5
CANDIDATES_CONSIDERED = 200
# Titles at least this similar are treated as the same story.
SAME_STORY_SIMILARITY = 0.8
TIER_POINTS = {"primary": 3, "reputable": 2, "aggregator": 1}
# The lowest rating (out of 5) an article may get for relevance and
# credibility and still be chosen.
LOWEST_GOOD_RATING = 3


def candidate_articles(plan, preset, now):
    """Return fresh, unused articles with enough text, newest first.

    plan may be None (a preview), and then nothing counts as used.
    """
    # Demo mode only uses the fictional demo articles; live mode never does.
    articles = Article.objects.filter(preset=preset, is_demo=settings.DEMO_MODE)
    if plan is not None:
        # Compared by address, so a story used under one topic is not used
        # again under another topic of the same plan.
        used = ArticleUse.objects.filter(plan=plan).values("article__url_hash")
        articles = articles.exclude(url_hash__in=used)
    freshness_hours = TOPIC_PRESETS[preset]["freshness_hours"]
    if freshness_hours > 0:
        articles = articles.filter(
            published_at__gte=now - timedelta(hours=freshness_hours)
        )
    newest = articles.order_by("-published_at")[:CANDIDATES_CONSIDERED]
    return [article for article in newest if len(article.text) >= MIN_TEXT_CHARACTERS]


def wanted_words(plan, preset, topic_name):
    """Return the words that show an article is on topic (lower case)."""
    words = list(TOPIC_PRESETS[preset]["keywords"])
    requirements = ""
    if plan is not None:
        requirements = plan.requirements
    for word in f"{requirements} {topic_name}".lower().split():
        word = word.strip(".,;:!?()\"'")
        if len(word) >= 4:
            words.append(word)
    return words


def score_article(article, words, preset, now):
    """Return a cheap score: higher is better. Each part adds at most 3."""
    score = TIER_POINTS.get(article.source_tier, 1)
    freshness_hours = TOPIC_PRESETS[preset]["freshness_hours"]
    if freshness_hours > 0:
        age_hours = (now - article.published_at).total_seconds() / 3600
        score = score + 2 * max(0, 1 - age_hours / freshness_hours)
    score = score + min(len(article.text), 4500) / 1500
    searched = f"{article.title} {article.text[:3000]}".lower()
    hits = 0
    for word in words:
        if word in searched:
            hits = hits + 1
    score = score + min(hits, 3)
    return score + min(article.popularity, 300) / 100


def same_story(first, second):
    """Return True if two articles' titles describe the same story."""
    ratio = SequenceMatcher(None, first.title_key, second.title_key).ratio()
    return ratio >= SAME_STORY_SIMILARITY


def make_shortlist(plan, preset, topic_name, now):
    """Return the best SHORTLIST_SIZE candidates, one per story."""
    words = wanted_words(plan, preset, topic_name)
    scored = []
    for article in candidate_articles(plan, preset, now):
        scored.append((score_article(article, words, preset, now), article))
    scored.sort(key=sort_by_score, reverse=True)
    shortlist = []
    for _, article in scored:
        is_repeat = False
        for chosen in shortlist:
            if same_story(article, chosen):
                is_repeat = True
        if not is_repeat:
            shortlist.append(article)
        if len(shortlist) == SHORTLIST_SIZE:
            break
    return shortlist


def sort_by_score(pair):
    """Return the score part of a (score, article) pair, for sorting."""
    return pair[0]


def is_good_enough(rating):
    """Return True if the model rated an article good enough to post about."""
    return (
        rating["relevance"] >= LOWEST_GOOD_RATING
        and rating["credibility"] >= LOWEST_GOOD_RATING
        and rating["verifiable"]
    )


def best_rated(shortlist, ratings):
    """Return the shortlisted article with the best passing rating, or None."""
    best_article = None
    best_total = 0
    for rating in ratings:
        number = rating["number"]
        if number < 1 or number > len(shortlist) or not is_good_enough(rating):
            continue
        total = rating["relevance"] + rating["credibility"] + rating["novelty"]
        if total > best_total:
            best_article = shortlist[number - 1]
            best_total = total
    return best_article
