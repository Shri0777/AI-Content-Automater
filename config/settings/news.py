"""Settings for reading news (imported by base.py)."""

from config.env import read_int, read_text

# Every request to a news site says who we are. Sites can then contact the
# operator or block us; set NEWS_USER_AGENT to include your own contact page.
NEWS_USER_AGENT = read_text(
    "NEWS_USER_AGENT", "AIContentAutomator/1.0 (news reader; self-hosted)"
)
# The most requests each kind of source may get per day (UTC), shared by all
# users. At the cap, reading stops and plans use articles already stored.
NEWS_DAILY_REQUEST_CAPS = {
    "rss": read_int("NEWS_RSS_DAILY_CAP", 500),
    "hackernews": read_int("NEWS_HACKERNEWS_DAILY_CAP", 300),
    "pages": read_int("NEWS_PAGES_DAILY_CAP", 300),
}
# Where the keyless Hacker News search API lives. Tests point it elsewhere.
HACKERNEWS_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
