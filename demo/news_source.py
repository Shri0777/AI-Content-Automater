"""A fake news source for demo mode and tests. It never uses the internet."""

from datetime import timedelta

from django.utils import timezone

from demo.articles import DEMO_ARTICLES
from newsroom.sources import NewsSource


class DemoNewsSource(NewsSource):
    """Returns the canned articles in demo/articles.py."""

    name = "demo"

    def fetch_articles(self, preset):
        """Return the canned articles for a preset, dated a few hours ago."""
        articles = []
        hours_ago = 1
        # Topics without their own demo articles (most of the catalogue, and
        # users' own topics) borrow the AI news ones.
        canned_articles = DEMO_ARTICLES.get(preset) or DEMO_ARTICLES["ai_news"]
        for number, canned in enumerate(canned_articles, start=1):
            articles.append(
                {
                    "url": f"https://example.com/demo/{preset}/{number}",
                    "title": canned["title"],
                    "source_name": "Demo News (fictional)",
                    "published_at": timezone.now() - timedelta(hours=hours_ago),
                    "text": canned["text"],
                }
            )
            hours_ago = hours_ago + 3
        return articles
