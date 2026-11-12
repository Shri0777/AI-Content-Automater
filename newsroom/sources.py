"""The base class for a place we read news articles from.

This is the adapter pattern: NewsSource is the base class, and each source
is one subclass (the demo one is in demo/news_source.py). Keyless real
sources and RSS feeds arrive in Phase 6.
"""


class NewsSource:
    """The base class every news source follows."""

    name = "unnamed"

    def fetch_articles(self, preset):
        """Return recent articles for a topic preset, such as "ai_news".

        Each article is a dict with: url, title, source_name, published_at
        (a timezone-aware datetime) and text. Raise core.errors.ProviderError
        if the source cannot be reached.
        """
        raise NotImplementedError("Each news source must define fetch_articles().")
