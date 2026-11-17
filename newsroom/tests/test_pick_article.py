"""Choosing an article for a plan's topic: the quality gates in order."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.errors import ProviderError
from credentials.services import save_credential
from demo.news_source import DemoNewsSource
from demo.text_model import DemoTextModel
from newsroom.ingest import url_fingerprint
from newsroom.models import Article
from newsroom.ranking import make_shortlist
from newsroom.services import pick_article, record_article_use
from notifications.models import Notification
from planning.models import ContentPlan, Topic
from studio.models import Post
from studio.runner import run_stage

LONG_TEXT = "A careful report with names, numbers and dates. " * 10


@pytest.fixture
def plan(db):
    """A saved plan belonging to a new user."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    return ContentPlan.objects.create(user=user, name="Tech news")


def topic_for(plan, preset):
    """Return a saved topic of plan following preset."""
    return Topic.objects.create(plan=plan, name="Topic", preset=preset)


class FixedRatings(DemoTextModel):
    """A fake model that gives every shortlisted article the same ratings."""

    def __init__(self, relevance, credibility, verifiable):
        super().__init__(None, "")
        self.rating = {
            "relevance": relevance,
            "credibility": credibility,
            "novelty": 3,
            "verifiable": verifiable,
        }
        self.seen = []

    def score_articles(self, articles, requirements):
        self.seen = list(articles)
        ratings = []
        for number in range(1, len(articles) + 1):
            rating = dict(self.rating)
            rating["number"] = number
            ratings.append(rating)
        return ratings


def good_model():
    """A fake model that rates everything good enough."""
    return FixedRatings(relevance=4, credibility=4, verifiable=True)


def store(preset, title, hours_ago, text=LONG_TEXT, tier="reputable"):
    """Save an article directly, as ingest would."""
    url = f"https://example.com/{preset}/{title.replace(' ', '-')}"
    return Article.objects.create(
        url_hash=url_fingerprint(url),
        url=url,
        title=title,
        title_key=title.lower(),
        source_name="Example",
        source_tier=tier,
        preset=preset,
        published_at=timezone.now() - timedelta(hours=hours_ago),
        text=text,
    )


@pytest.fixture
def no_sources(monkeypatch):
    """Read no sources, so a test sees only the articles it stores itself."""
    monkeypatch.setattr("newsroom.ingest.get_sources", empty_source_list)


def empty_source_list(preset):
    """Return no sources at all."""
    return []


def test_an_article_from_the_demo_source_is_picked(plan):
    article = pick_article(plan, topic_for(plan, "ai_news"), good_model())

    assert article.preset == "ai_news"


def test_a_plan_never_gets_the_same_article_twice(plan):
    topic = topic_for(plan, "ai_news")
    titles = []
    for _ in range(3):
        article = pick_article(plan, topic, good_model())
        record_article_use(plan, article)
        titles.append(article.title)

    assert len(set(titles)) == 3
    assert pick_article(plan, topic, good_model()) is None


def test_articles_are_stored_once_however_often_sources_are_read(plan, settings):
    topic = topic_for(plan, "layoffs")
    pick_article(plan, topic, good_model())
    Article.objects.update(fetched_at=timezone.now())
    pick_article(plan, topic, good_model())

    assert Article.objects.filter(preset="layoffs").count() == 3


def test_old_news_is_not_used(plan, no_sources):
    store("ai_news", "Old story", hours_ago=14 * 24)

    assert pick_article(plan, topic_for(plan, "ai_news"), good_model()) is None


def test_evergreen_tips_never_go_stale(plan, no_sources):
    store("linux_tips", "An old but useful tip", hours_ago=730 * 24)

    article = pick_article(plan, topic_for(plan, "linux_tips"), good_model())

    assert article.title == "An old but useful tip"


def test_an_article_with_too_little_text_is_not_used(plan, no_sources):
    store("ai_news", "Only a headline", hours_ago=1, text="Too short to check.")

    assert pick_article(plan, topic_for(plan, "ai_news"), good_model()) is None


@pytest.mark.parametrize(
    "relevance, credibility, verifiable",
    [(2, 5, True), (5, 2, True), (5, 5, False)],
)
def test_nothing_is_picked_unless_the_model_rates_it_good_enough(
    plan, no_sources, relevance, credibility, verifiable
):
    store("ai_news", "A story", hours_ago=1)
    model = FixedRatings(relevance, credibility, verifiable)

    assert pick_article(plan, topic_for(plan, "ai_news"), model) is None


def test_the_same_story_from_two_outlets_is_shortlisted_once(plan, no_sources):
    store("ai_news", "big lab releases new model today", hours_ago=1)
    store("ai_news", "big lab releases a new model today", hours_ago=2)
    store("ai_news", "chip maker reports record quarter", hours_ago=3)

    shortlist = make_shortlist(plan, "ai_news", "AI", timezone.now())

    assert len(shortlist) == 2


def test_a_trusted_on_topic_article_ranks_above_an_aggregated_one(plan, no_sources):
    store("ai_news", "random link roundup", hours_ago=1, tier="aggregator")
    on_topic = store("ai_news", "new llm model from openai", hours_ago=2)

    shortlist = make_shortlist(plan, "ai_news", "AI", timezone.now())

    assert shortlist[0] == on_topic


class BrokenSource(DemoNewsSource):
    """A source that is always down."""

    def fetch_articles(self, preset):
        raise ProviderError("The source is down.")


def test_a_failing_source_is_skipped(plan, monkeypatch):
    def broken_then_working(preset):
        return [BrokenSource(), DemoNewsSource()]

    monkeypatch.setattr("newsroom.ingest.get_sources", broken_then_working)

    assert pick_article(plan, topic_for(plan, "ai_news"), good_model()) is not None


def test_a_post_with_no_good_enough_article_is_skipped_never_filled(plan, monkeypatch):
    def rate_everything_low(self, articles, requirements):
        return FixedRatings(1, 1, False).score_articles(articles, requirements)

    monkeypatch.setattr(DemoTextModel, "score_articles", rate_everything_low)
    save_credential(plan.user, {"kind": "text", "adapter": "demo"})
    post = Post.objects.create(
        user=plan.user, plan=plan, topic=topic_for(plan, "ai_news"), demo_mode=True
    )

    assert run_stage(post.id) == "skipped"

    post.refresh_from_db()
    assert post.article is None
    assert post.versions.count() == 0
    assert "rather than posting filler" in post.status_reason
    assert Notification.objects.filter(kind="post_skipped").count() == 1


def test_a_story_used_under_one_topic_is_not_used_again_under_another(plan, no_sources):
    story = store("ai_news", "Lab cuts 100 jobs", hours_ago=1)
    record_article_use(plan, story)
    copy = store("layoffs", "Lab cuts 100 jobs", hours_ago=1)
    copy.url_hash = story.url_hash
    copy.save()

    assert pick_article(plan, topic_for(plan, "layoffs"), good_model()) is None
