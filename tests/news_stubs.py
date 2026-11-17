"""Feed, page and search answers shaped like the real news sources.

RSS_FEED follows RSS 2.0 with content:encoded (as Linux Handbook's feed
does), ATOM_FEED follows Atom (as The Verge's does), and HACKERNEWS_ANSWER
has the fields the Hacker News search API returned on 2026-11-17.
"""

import json
from datetime import UTC, datetime, timedelta

LONG_HTML = "<p>" + "A careful report with names, numbers and dates. " * 10 + "</p>"


def rss_date(hours_ago):
    """Return an RSS (RFC 822) date hours_ago hours before now."""
    moment = datetime.now(UTC) - timedelta(hours=hours_ago)
    return moment.strftime("%a, %d %b %Y %H:%M:%S +0000")


def rss_feed(base_url):
    """Return an RSS feed with two good items and one without a link."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Example Feed</title>
<item><title>New open model beats the old one</title>
<link>{base_url}/articles/1</link><pubDate>{rss_date(2)}</pubDate>
<content:encoded><![CDATA[{LONG_HTML}<script>alert(1)</script>]]></content:encoded>
</item>
<item><title>Short item that needs its page read</title>
<link>{base_url}/articles/2</link><pubDate>{rss_date(3)}</pubDate>
<description>Only one line.</description></item>
<item><title>Item without a link</title><pubDate>{rss_date(1)}</pubDate></item>
</channel></rss>""".encode()


ATOM_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Example Atom</title>
<entry><title>Atom story about a chip</title>
<link rel="alternate" href="https://example.com/atom/1"/>
<published>{(datetime.now(UTC) - timedelta(hours=1)).isoformat()}</published>
<content type="html">{LONG_HTML.replace("<", "&lt;").replace(">", "&gt;")}</content>
</entry></feed>""".encode()

# An XML file that would expand to gigabytes in a naive parser.
XML_BOMB = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
<rss><channel><item><title>&lol2;</title></item></channel></rss>"""

ARTICLE_PAGE = f"""<html><head><script>var x = 1;</script></head><body>
<nav>Home | News | About</nav>
<article><h1>Short item that needs its page read</h1>{LONG_HTML}</article>
<footer>Copyright</footer></body></html>""".encode()

ALLOW_ALL_ROBOTS = b"User-agent: *\nDisallow: /admin/\n"
BLOCK_AI_ROBOTS = (
    b"User-agent: *\nDisallow: /admin/\n\nUser-agent: GPTBot\nDisallow: /\n"
)


def hackernews_answer(base_url):
    """Return a search answer with one story and one "Ask HN" (no link)."""
    created = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hits = [
        {
            "title": "Company lays off 200 engineers",
            "url": f"{base_url}/hn-story",
            "created_at": created,
            "points": 120,
            "objectID": "1",
        },
        {"title": "Ask HN: Who is hiring?", "url": None, "created_at": created},
    ]
    return json.dumps({"hits": hits}).encode()
