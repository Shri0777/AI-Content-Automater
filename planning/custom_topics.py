"""Topics users write themselves: their own name, search words and instructions.

A custom topic is a preset whose key is "custom-<topic id>". It reads Hacker
News for the topic's words, plus a few broad tech news feeds, keeping only
the items that mention one of the words (newsroom/ingest.py). The user's
instructions are added to the plan's own instructions whenever articles are
chosen or posts are written for this topic (requirements_for).
"""

from newsroom.presets import CUSTOM_PREFIX, get_preset
from planning.models import Topic

# Wide tech feeds, filtered by the topic's words. Checked on 2026-11-17.
BROAD_FEEDS = [
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("TechCrunch", "https://techcrunch.com/category/startups/feed/"),
    ("InfoQ", "https://www.infoq.com/feed/"),
]
CUSTOM_FRESHNESS_HOURS = 168
MAX_WORDS = 10


def custom_key(topic):
    """Return the preset key of a custom topic."""
    return f"{CUSTOM_PREFIX}{topic.id.hex}"


def search_words_of(text):
    """Return the comma-separated words of text, trimmed, without blanks."""
    words = []
    for word in text.split(","):
        if word.strip():
            words.append(word.strip())
    return words[:MAX_WORDS]


def custom_sources(words):
    """Return the sources for a custom topic: a Hacker News search and broad feeds."""
    sources = [
        {
            "type": "hackernews",
            "name": "Hacker News",
            "query": " ".join(words),
            "tier": "aggregator",
        }
    ]
    for name, url in BROAD_FEEDS:
        sources.append(
            {
                "type": "rss",
                "name": name,
                "url": url,
                "tier": "reputable",
                "broad": True,
            }
        )
    return sources


def custom_preset(key):
    """Return the preset for a custom topic's key, or None if there is none."""
    topic = Topic.objects.filter(preset=key).first()
    if topic is None:
        return None
    words = search_words_of(topic.search_words)
    return {
        "label": topic.name,
        "category": "Your topics",
        "description": topic.instructions[:120],
        "kind": "news",
        "freshness_hours": CUSTOM_FRESHNESS_HOURS,
        "strict_review": False,
        "keywords": [word.lower() for word in words],
        "sources": custom_sources(words),
    }


def requirements_for(plan, topic):
    """Return the plan's instructions plus the topic's own, for the AI."""
    parts = [plan.requirements.strip()]
    if topic is not None and topic.instructions.strip():
        parts.append(f"For the topic '{topic.name}': {topic.instructions.strip()}")
    return "\n".join(part for part in parts if part)


def is_known_preset(key):
    """Return True if key is a built-in preset or an existing custom topic."""
    return get_preset(key) is not None
