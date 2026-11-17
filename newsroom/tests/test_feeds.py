"""Reading feeds and turning HTML into text, safely."""

import pytest

from core.errors import ProviderError
from newsroom.extract import html_to_text
from newsroom.feeds import parse_feed
from tests.news_stubs import ARTICLE_PAGE, ATOM_FEED, XML_BOMB, rss_feed


def test_rss_items_are_read_with_their_full_text():
    items = parse_feed(rss_feed("https://example.com"))

    assert [item["title"] for item in items] == [
        "New open model beats the old one",
        "Short item that needs its page read",
    ]
    assert items[0]["text"].startswith("A careful report")
    assert "alert" not in items[0]["text"]
    assert items[0]["published_at"].tzinfo is not None


def test_atom_entries_are_read():
    items = parse_feed(ATOM_FEED)

    assert items[0]["url"] == "https://example.com/atom/1"
    assert len(items[0]["text"]) > 280


def test_an_xml_bomb_is_refused_instead_of_expanded():
    with pytest.raises(ProviderError):
        parse_feed(XML_BOMB)


def test_something_that_is_not_xml_is_refused():
    with pytest.raises(ProviderError, match="not valid XML"):
        parse_feed(b"<html>Sorry, we are down</html")


def test_page_text_keeps_the_article_and_drops_menus_and_scripts():
    text = html_to_text(ARTICLE_PAGE.decode())

    assert text.startswith("Short item that needs its page read")
    assert "Home | News" not in text
    assert "var x" not in text
    assert "Copyright" not in text
