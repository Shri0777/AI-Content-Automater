"""Read RSS 2.0 and Atom feeds into plain article dicts.

Feeds are XML from the internet, so they are parsed with defusedxml, which
refuses the XML tricks that can exhaust memory or read local files.
"""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from core.errors import ProviderError
from newsroom.extract import html_to_text

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT_ENCODED = "{http://purl.org/rss/1.0/modules/content/}encoded"


def parse_date(text):
    """Return a timezone-aware datetime from an RSS or Atom date, or None."""
    if not text:
        return None
    text = text.strip()
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            moment = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def atom_link(entry):
    """Return the main link of an Atom entry."""
    for link in entry.findall(f"{ATOM}link"):
        if link.get("rel", "alternate") == "alternate":
            return link.get("href", "")
    return ""


def read_rss_item(item):
    """Return the parts of one RSS <item>."""
    html = item.findtext(CONTENT_ENCODED) or item.findtext("description") or ""
    return {
        "url": (item.findtext("link") or "").strip(),
        "title": (item.findtext("title") or "").strip(),
        "published_at": parse_date(item.findtext("pubDate")),
        "text": html_to_text(html),
    }


def read_atom_entry(entry):
    """Return the parts of one Atom <entry>."""
    html = entry.findtext(f"{ATOM}content") or entry.findtext(f"{ATOM}summary") or ""
    published = entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")
    return {
        "url": atom_link(entry).strip(),
        "title": (entry.findtext(f"{ATOM}title") or "").strip(),
        "published_at": parse_date(published),
        "text": html_to_text(html),
    }


def parse_feed(content):
    """Return the usable items of an RSS or Atom feed.

    Items without a link, title or date are left out.
    """
    try:
        root = ElementTree.fromstring(content)
    except (ElementTree.ParseError, DefusedXmlException):
        raise ProviderError("The feed is not valid XML.") from None
    items = []
    for item in root.iter("item"):
        items.append(read_rss_item(item))
    for entry in root.iter(f"{ATOM}entry"):
        items.append(read_atom_entry(entry))
    usable = []
    for item in items:
        if item["url"].startswith("http") and item["title"] and item["published_at"]:
            usable.append(item)
    return usable
