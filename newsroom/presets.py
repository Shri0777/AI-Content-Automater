"""Topic presets: ready-made kinds of topic a plan can follow.

Presets are plain data. "news" topics only use recent articles (within
freshness_hours). "evergreen" topics, such as tips, never go stale.
"""

TOPIC_PRESETS = {
    "job_hiring": {"label": "Job hiring", "kind": "news", "freshness_hours": 72},
    "layoffs": {"label": "Layoffs", "kind": "news", "freshness_hours": 48},
    "linux_tips": {"label": "Linux tips", "kind": "evergreen", "freshness_hours": 0},
    "ai_news": {"label": "AI news", "kind": "news", "freshness_hours": 72},
}

PRESET_CHOICES = [(key, preset["label"]) for key, preset in TOPIC_PRESETS.items()]
