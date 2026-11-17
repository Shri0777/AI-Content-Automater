"""Turn HTML (a web page or a feed's HTML content) into plain readable text.

This uses Python's own html.parser, so no extra library is needed. It keeps
the text of paragraphs, headings, list items and code blocks, and ignores
scripts, styles, menus, headers, footers, forms and sidebars. When a page
has an <article> element, only the text inside it is kept.
"""

from html.parser import HTMLParser

# Text inside these is never content.
SKIPPED_TAGS = [
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "form",
    "aside",
    "noscript",
]
# Each of these starts a new paragraph of text.
BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "pre", "blockquote", "div", "br"]


class TextCollector(HTMLParser):
    """Collects readable text, paragraph by paragraph, while reading HTML."""

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.article_depth = 0
        self.saw_article = False
        self.all_paragraphs = [""]
        self.article_paragraphs = [""]

    def handle_starttag(self, tag, attrs):
        """Note where skipped parts and the article start."""
        if tag in SKIPPED_TAGS:
            self.skip_depth = self.skip_depth + 1
        if tag == "article":
            self.article_depth = self.article_depth + 1
            self.saw_article = True
        if tag in BLOCK_TAGS:
            self.all_paragraphs.append("")
            self.article_paragraphs.append("")

    def handle_endtag(self, tag):
        """Note where skipped parts and the article end."""
        if tag in SKIPPED_TAGS and self.skip_depth > 0:
            self.skip_depth = self.skip_depth - 1
        if tag == "article" and self.article_depth > 0:
            self.article_depth = self.article_depth - 1

    def handle_data(self, data):
        """Add a piece of text to the current paragraph, unless it is skipped."""
        if self.skip_depth > 0:
            return
        self.all_paragraphs[-1] = self.all_paragraphs[-1] + data
        if self.article_depth > 0:
            self.article_paragraphs[-1] = self.article_paragraphs[-1] + data


def tidy(paragraphs):
    """Return non-empty paragraphs, each on one line, joined by blank lines."""
    kept = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if words:
            kept.append(" ".join(words))
    return "\n\n".join(kept)


def html_to_text(html):
    """Return the readable text of an HTML page or snippet."""
    collector = TextCollector()
    collector.feed(html)
    collector.close()
    if collector.saw_article:
        article_text = tidy(collector.article_paragraphs)
        if article_text:
            return article_text
    return tidy(collector.all_paragraphs)
