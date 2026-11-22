"""The base class for a place we read news from, and the keyless sources.

This is the adapter pattern: NewsSource is the base class, and each kind of
source is one subclass: RssSource (a site's feed), HackerNewsSource (Hacker
News search) and DemoNewsSource (demo/news_source.py, canned articles).
get_sources(preset) builds them from the preset's data (newsroom/presets.py).
"""

from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.utils import timezone

from core import web
from newsroom.feeds import parse_date, parse_feed
from newsroom.fetching import fetch_feed, get_with_redirects, user_agent_header
from newsroom.presets import get_preset

HACKERNEWS_STORIES_PER_READ = 30
HACKERNEWS_MIN_POINTS = 5


class NewsSource:
    """The base class every news source follows."""

    name = "unnamed"
    tier = "reputable"
    # A broad source covers many topics; only items on the topic are kept.
    broad = False

    def fetch_articles(self, preset):
        """Return recent articles for a topic preset, such as "ai_news".

        Each article is a dict with: url, title, source_name, published_at
        (a timezone-aware datetime), text ("" if not known yet), and
        optionally popularity. Raise core.errors.ProviderError if the source
        cannot be read.
        """
        raise NotImplementedError("Each news source must define fetch_articles().")


class RssSource(NewsSource):
    """A site's own RSS or Atom feed."""

    def __init__(self, config):
        self.name = config["name"]
        self.url = config["url"]
        self.tier = config["tier"]
        self.broad = config.get("broad", False)

    def fetch_articles(self, preset):
        """Return the feed's items, or [] if it has not changed."""
        content = fetch_feed(self.url, preset)
        if content is None:
            return []
        items = parse_feed(content)
        for item in items:
            item["source_name"] = self.name
        return items


def site_name(url):
    """Return the site part of url without "www.", for example "abc.net.au"."""
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.")


class HackerNewsSource(NewsSource):
    """Hacker News stories matching a search, through its public search API.

    The stories link to other sites, so each article is credited to that
    site; its text is read from the page later, where robots.txt allows.
    """

    def __init__(self, config):
        self.name = config["name"]
        self.query = config["query"]
        self.tier = config["tier"]

    def search_url(self, preset_hours):
        """Return the search address for recent, upvoted stories."""
        since = timezone.now() - timedelta(hours=preset_hours or 72)
        params = {
            "query": self.query,
            "tags": "story",
            "hitsPerPage": HACKERNEWS_STORIES_PER_READ,
            "numericFilters": f"created_at_i>{int(since.timestamp())},"
            f"points>={HACKERNEWS_MIN_POINTS}",
        }
        return f"{settings.HACKERNEWS_SEARCH_URL}?{urlencode(params)}"

    def fetch_articles(self, preset):
        """Return recent stories that link to an article."""
        url = self.search_url(get_preset(preset)["freshness_hours"])
        answer = get_with_redirects(url, user_agent_header(), "hackernews")
        found = web.parse_json(answer.content)
        articles = []
        for hit in found.get("hits", []):
            link = hit.get("url") or ""
            published_at = parse_date(hit.get("created_at"))
            if not link.startswith("http") or not hit.get("title") or not published_at:
                continue
            articles.append(
                {
                    "url": link,
                    "title": hit["title"],
                    "source_name": site_name(link),
                    "published_at": published_at,
                    "text": "",
                    "popularity": int(hit.get("points") or 0),
                }
            )
        return articles


SOURCE_CLASSES = {"rss": RssSource, "hackernews": HackerNewsSource}


def get_sources(preset):
    """Return the sources to read for a preset (only the demo one in demo mode)."""
    if settings.DEMO_MODE:
        # Imported here because demo/news_source.py imports this file.
        from demo.news_source import DemoNewsSource

        return [DemoNewsSource()]
    sources = []
    for config in get_preset(preset)["sources"]:
        sources.append(SOURCE_CLASSES[config["type"]](config))
    return sources
