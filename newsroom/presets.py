"""Topic presets: ready-made kinds of topic a plan can follow.

Presets are plain data. "news" topics only use recent articles (within
freshness_hours). "evergreen" topics, such as tips, never go stale.

Each preset lists its sources. Every source here needs no API key:
- "rss": a site's own RSS or Atom feed.
- "hackernews": Hacker News stories found through its public search API.
Each feed was checked by hand on 2026-11-17 (it answered and had items).
Google News RSS and VentureBeat were left out: both refused automated
readers (HTTP 429) that day.

A "broad" source covers all of tech, so only its items that mention one of
the preset's keywords are kept. The Register and Computerworld were added
for layoffs and hiring because their feeds publish full text, while
TechCrunch's tag feeds publish one line and its pages are closed to AI
readers.

tier says how much a source is trusted when ranking articles:
"primary" (the people involved), "reputable" (an established publication)
or "aggregator" (links collected from elsewhere). keywords help rank
articles that are really about the topic.
"""

TOPIC_PRESETS = {
    "job_hiring": {
        "label": "Job hiring",
        "kind": "news",
        "freshness_hours": 72,
        "keywords": ["hiring", "hire", "hires", "recruit", "openings"],
        "sources": [
            {
                "type": "rss",
                "name": "TechCrunch",
                "url": "https://techcrunch.com/tag/hiring/feed/",
                "tier": "reputable",
            },
            {
                "type": "rss",
                "name": "The Register",
                "url": "https://www.theregister.com/headlines.atom",
                "tier": "reputable",
                "broad": True,
            },
            {
                "type": "rss",
                "name": "Computerworld",
                "url": "https://www.computerworld.com/feed/",
                "tier": "reputable",
                "broad": True,
            },
            {
                "type": "hackernews",
                "name": "Hacker News",
                "query": "hiring",
                "tier": "aggregator",
            },
        ],
    },
    "layoffs": {
        "label": "Layoffs",
        "kind": "news",
        "freshness_hours": 48,
        "keywords": ["layoff", "layoffs", "laid off", "job cuts", "redundan"],
        "sources": [
            {
                "type": "rss",
                "name": "TechCrunch",
                "url": "https://techcrunch.com/tag/layoffs/feed/",
                "tier": "reputable",
            },
            {
                "type": "rss",
                "name": "The Register",
                "url": "https://www.theregister.com/headlines.atom",
                "tier": "reputable",
                "broad": True,
            },
            {
                "type": "rss",
                "name": "Computerworld",
                "url": "https://www.computerworld.com/feed/",
                "tier": "reputable",
                "broad": True,
            },
            {
                "type": "hackernews",
                "name": "Hacker News",
                "query": "layoffs",
                "tier": "aggregator",
            },
        ],
    },
    "linux_tips": {
        "label": "Linux tips",
        "kind": "evergreen",
        "freshness_hours": 0,
        "keywords": ["linux", "command", "terminal", "shell", "bash", "ubuntu"],
        "sources": [
            {
                "type": "rss",
                "name": "Linux Handbook",
                "url": "https://linuxhandbook.com/rss/",
                "tier": "reputable",
            },
            {
                "type": "rss",
                "name": "It's FOSS",
                "url": "https://feed.itsfoss.com/",
                "tier": "reputable",
            },
            {
                "type": "rss",
                "name": "nixCraft",
                "url": "https://www.cyberciti.com/feed/",
                "tier": "reputable",
            },
        ],
    },
    "ai_news": {
        "label": "AI news",
        "kind": "news",
        "freshness_hours": 72,
        "keywords": ["ai", "model", "llm", "openai", "anthropic", "machine learning"],
        "sources": [
            {
                "type": "rss",
                "name": "MIT Technology Review",
                "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
                "tier": "reputable",
            },
            {
                "type": "rss",
                "name": "The Verge",
                "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
                "tier": "reputable",
            },
            {
                "type": "rss",
                "name": "TechCrunch",
                "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
                "tier": "reputable",
            },
            {
                "type": "hackernews",
                "name": "Hacker News",
                "query": "AI",
                "tier": "aggregator",
            },
        ],
    },
}

PRESET_CHOICES = [(key, preset["label"]) for key, preset in TOPIC_PRESETS.items()]
