"""Download feeds and article pages politely and safely.

- Every request says who we are (NEWS_USER_AGENT) and uses a daily budget.
- Feeds are asked "only if changed" (ETag and Last-Modified), so an unchanged
  feed costs the site almost nothing.
- Redirects are followed by hand, at most MAX_REDIRECTS times, and every new
  address is checked by core/web.py like the first (no private addresses).
- Article pages are only read where the site's robots.txt allows our reader
  AND the common AI crawlers. Several news sites block AI crawlers; we treat
  that as "please do not feed our pages to an AI", and use only what their
  feed itself publishes.
"""

from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core import web
from core.errors import ProviderError
from newsroom.budgets import use_request_budget
from newsroom.models import FeedState

MAX_REDIRECTS = 3
AI_CRAWLERS = ["GPTBot", "ClaudeBot", "anthropic-ai", "Google-Extended", "CCBot"]
ROBOTS_CACHE_SECONDS = 24 * 60 * 60


class OverBudget(ProviderError):
    """Raised when today's request cap for a kind of source is used up."""


def get_with_redirects(url, headers, source):
    """GET url, following up to MAX_REDIRECTS checked redirects; return the Answer."""
    for _ in range(MAX_REDIRECTS + 1):
        if not use_request_budget(source):
            raise OverBudget(f"Today's request budget for {source} is used up.")
        try:
            return web.send("GET", url, headers)
        except web.Redirected as redirect:
            if not redirect.location:
                raise
            url = urljoin(url, redirect.location)
    raise ProviderError("The address redirected too many times.")


def fetch_feed(url, preset):
    """Return the feed's bytes, or None if unchanged since preset last read it."""
    state, _ = FeedState.objects.get_or_create(url=url, preset=preset)
    headers = {"User-Agent": settings.NEWS_USER_AGENT}
    if state.etag:
        headers["If-None-Match"] = state.etag
    if state.last_modified:
        headers["If-Modified-Since"] = state.last_modified
    answer = get_with_redirects(url, headers, "rss")
    state.checked_at = timezone.now()
    if answer.status == 304:
        state.save(update_fields=["checked_at"])
        return None
    state.etag = answer.headers.get("etag", "")[:300]
    state.last_modified = answer.headers.get("last-modified", "")[:100]
    state.save()
    return answer.content


def read_robots_rules(url):
    """Return the robots.txt lines of url's site (cached for a day)."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    cache_key = f"robots:{parts.netloc}"
    lines = cache.get(cache_key)
    if lines is None:
        try:
            content = get_with_redirects(
                robots_url, user_agent_header(), "pages"
            ).content
            lines = content.decode(errors="replace").splitlines()
        except OverBudget:
            raise
        except ProviderError:
            # No robots.txt (or an error page) means no rules were published.
            lines = []
        cache.set(cache_key, lines, ROBOTS_CACHE_SECONDS)
    return lines


def user_agent_header():
    """Return the header that tells sites who is reading."""
    return {"User-Agent": settings.NEWS_USER_AGENT}


def may_read_page(url):
    """Return True if url's site lets us, and AI crawlers, read the page."""
    rules = RobotFileParser()
    rules.parse(read_robots_rules(url))
    if not rules.can_fetch(settings.NEWS_USER_AGENT, url):
        return False
    for crawler in AI_CRAWLERS:
        if not rules.can_fetch(crawler, url):
            return False
    return True


def fetch_page_html(url):
    """Return the page's HTML text, or "" if robots.txt asks us not to read it."""
    if not may_read_page(url):
        return ""
    answer = get_with_redirects(url, user_agent_header(), "pages")
    return answer.content.decode(errors="replace")
