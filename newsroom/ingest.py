"""Read each topic's sources into the shared article store ("ingest").

Ingest runs every 30 minutes for the presets that active plans use (so a
preset nobody follows costs nothing), and right before a post needs an
article if the last read is older than INGEST_EVERY. Fetch volume grows
with topics, not with users: one read serves every plan.

Each article is stored once. The same story from several outlets (the
same title once punctuation and case are removed) is stored only once.
Articles whose feed gave little text get their page read, within budget and
only where robots.txt allows (newsroom/fetching.py).
"""

import hashlib
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

from core.disk import disk_is_nearly_full
from core.errors import ProviderError
from newsroom.extract import html_to_text
from newsroom.fetching import OverBudget, fetch_page_html
from newsroom.models import Article, IngestRecord
from newsroom.presets import TOPIC_PRESETS
from newsroom.sources import get_sources
from planning.models import Topic

INGEST_EVERY = timedelta(minutes=30)
# Shorter text than this is not enough to write an accurate post from.
MIN_TEXT_CHARACTERS = 280
PAGES_PER_RUN = 8
DUPLICATE_WINDOW = timedelta(days=7)


def url_fingerprint(url):
    """Return a short fixed-length fingerprint of an article's address."""
    return hashlib.sha256(url.encode()).hexdigest()


def title_key(title):
    """Return title in lower case with only letters, digits and single spaces."""
    for separator in [" - ", " | ", " — "]:
        # "Big news - Example Times": drop the outlet's name at the end.
        if separator in title:
            title = title.rsplit(separator, 1)[0]
    kept = ""
    for character in title.lower():
        if character.isalnum():
            kept = kept + character
        else:
            kept = kept + " "
    return " ".join(kept.split())[:500]


def is_copy_of_another_story(preset, item, key):
    """Return True if another outlet's article with the same title is stored."""
    return (
        Article.objects.filter(
            preset=preset,
            title_key=key,
            published_at__gte=item["published_at"] - DUPLICATE_WINDOW,
        )
        .exclude(url_hash=url_fingerprint(item["url"]))
        .exists()
    )


def update_existing(article, item):
    """Refresh a stored article with newer details from its source."""
    article.popularity = max(article.popularity, item.get("popularity", 0))
    if len(item["text"]) > len(article.text):
        article.text = item["text"]
        article.text_source = "feed"
    article.save()


def save_article(preset, item, source):
    """Store one article from source; return True if it was new."""
    existing = Article.objects.filter(
        url_hash=url_fingerprint(item["url"]), preset=preset
    ).first()
    if existing is not None:
        update_existing(existing, item)
        return False
    key = title_key(item["title"])
    if is_copy_of_another_story(preset, item, key):
        return False
    try:
        Article.objects.create(
            url_hash=url_fingerprint(item["url"]),
            url=item["url"][:1000],
            title=item["title"][:500],
            title_key=key,
            source_name=item["source_name"][:200],
            source_tier=source.tier,
            preset=preset,
            published_at=item["published_at"],
            popularity=item.get("popularity", 0),
            is_demo=source.name == "demo",
            text=item["text"],
            text_source="feed" if item["text"] else "",
        )
    except IntegrityError:
        # Another worker stored the same article a moment ago.
        return False
    return True


def read_missing_texts(preset):
    """Read the pages of articles whose feed gave too little text."""
    articles = Article.objects.filter(preset=preset, page_checked=False).order_by(
        "-popularity", "-published_at"
    )
    for article in articles[: PAGES_PER_RUN * 3]:
        if len(article.text) >= MIN_TEXT_CHARACTERS:
            continue
        try:
            page_text = html_to_text(fetch_page_html(article.url))
        except OverBudget:
            return
        except ProviderError:
            page_text = ""
        article.page_checked = True
        if len(page_text) > len(article.text):
            article.text = page_text
            article.text_source = "page"
        article.save()


def mentions_topic(preset, item):
    """Return True if the item's title or text mentions a preset keyword."""
    searched = f"{item['title']} {item['text'][:3000]}".lower()
    for keyword in TOPIC_PRESETS[preset]["keywords"]:
        if keyword in searched:
            return True
    return False


def ingest_preset(preset):
    """Read every source of preset; return how many new articles were stored."""
    new_count = 0
    for source in get_sources(preset):
        try:
            items = source.fetch_articles(preset)
        except ProviderError:
            # One failing or over-budget source never stops the others.
            continue
        for item in items:
            if source.broad and not mentions_topic(preset, item):
                continue
            if save_article(preset, item, source):
                new_count = new_count + 1
    read_missing_texts(preset)
    IngestRecord.objects.update_or_create(
        preset=preset, defaults={"finished_at": timezone.now()}
    )
    return new_count


def ensure_recent_ingest(preset):
    """Read preset's sources now if the last read is older than INGEST_EVERY."""
    record = IngestRecord.objects.filter(preset=preset).first()
    if record is None or record.finished_at < timezone.now() - INGEST_EVERY:
        ingest_preset(preset)


def ingest_active_presets():
    """Read the sources of every preset an active plan follows.

    Nothing is read while the disk is nearly full (core/disk.py).
    """
    if disk_is_nearly_full():
        return 0
    presets = set(
        Topic.objects.filter(plan__paused=False).values_list("preset", flat=True)
    )
    new_count = 0
    for preset in sorted(presets):
        new_count = new_count + ingest_preset(preset)
    return new_count
