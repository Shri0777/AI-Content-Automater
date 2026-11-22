"""Topic presets: ready-made kinds of topic a plan can follow.

The presets themselves are plain data in newsroom/topics.json, grouped into
categories for the topic picker. "news" topics only use recent articles
(within freshness_hours). "evergreen" topics, such as tips, never go stale.

Each preset lists its sources. Every source needs no API key:
- "rss": a site's own RSS or Atom feed.
- "hackernews": Hacker News stories found through its public search API.
Every feed was checked by hand on 2026-11-17 (it answered and had items).
Google News RSS and VentureBeat were left out: both refused automated
readers (HTTP 429) that day; swift.org's feed was empty.

A "broad" source covers more than the topic, so only its items that mention
one of the preset's keywords are kept.

strict_review makes the review stricter (studio/verdicts.py): for topics
that name real companies, people or money (layoffs, security, funding) and
for Linux tips, whose commands people run on their own computers.

tier says how much a source is trusted when ranking articles:
"primary" (the people involved), "reputable" (an established publication)
or "aggregator" (links collected from elsewhere). keywords help rank
articles that are really about the topic.

A user's own topics are presets too: get_preset() builds one for any key
that starts with CUSTOM_PREFIX (see planning/custom_topics.py).
"""

import json
from pathlib import Path

CATALOGUE = json.loads(
    (Path(__file__).parent / "topics.json").read_text(encoding="utf-8")
)
TOPIC_CATEGORIES = CATALOGUE["categories"]
TOPIC_PRESETS = CATALOGUE["topics"]
PRESET_CHOICES = [(key, preset["label"]) for key, preset in TOPIC_PRESETS.items()]
CUSTOM_PREFIX = "custom-"


def get_preset(key):
    """Return the preset for key (built-in or a user's own topic), or None."""
    if key in TOPIC_PRESETS:
        return TOPIC_PRESETS[key]
    if key.startswith(CUSTOM_PREFIX):
        # Imported here: planning imports this file for its topic choices.
        from planning.custom_topics import custom_preset

        return custom_preset(key)
    return None
