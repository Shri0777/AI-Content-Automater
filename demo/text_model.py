"""A fake text model for demo mode and tests.

It fills in templates instead of calling an AI, so its answers are always
the same for the same article. Posts it writes are canned, not AI output.
"""

from studio.post_content import trim_words, word_count
from studio.text_models import TextModel

MAX_HEADLINE_LENGTH = 90
DEMO_POINTS = 4
# The demo articles are fiction written for this app; their sentences are long.
MAX_POINT_LENGTH = 200
# Short enough for one slide (studio/post_content.py asks for at most 32).
MAX_POINT_WORDS = 28


def sentences_of(text):
    """Return the sentences of text, each ending with a full stop."""
    sentences = []
    for sentence in text.replace("\n", " ").split(". "):
        sentence = sentence.strip().rstrip(".")
        if sentence:
            sentences.append(f"{sentence}.")
    return sentences


def key_sentences(text):
    """Return up to DEMO_POINTS short sentences from text, as key points."""
    points = []
    for sentence in sentences_of(text):
        short_enough = len(sentence) <= MAX_POINT_LENGTH
        if (
            20 <= len(sentence)
            and short_enough
            and word_count(sentence) <= MAX_POINT_WORDS
        ):
            points.append(sentence)
        if len(points) == DEMO_POINTS:
            break
    return points


def demo_figure(article):
    """Return the first number in the title as the figure, or {} if none."""
    words = article.title.split()
    for index, word in enumerate(words):
        if any(character.isdigit() for character in word):
            label = " ".join(words[index + 1 : index + 6]) or article.title
            return {"value": word, "label": label, "compare": []}
    return {}


def demo_takeaway(article, points):
    """Return the article's last sentence not already a point, for the closing
    slide, or "" if every sentence is a point."""
    for sentence in reversed(sentences_of(article.text)):
        if sentence not in points:
            return trim_words(sentence, 140)
    return ""


class DemoTextModel(TextModel):
    """Writes and reviews posts from templates, without any AI."""

    def check_connection(self):
        """The demo model is always available."""

    def describe(self):
        """Return "demo": there is no real model behind it."""
        return "demo"

    def score_articles(self, articles, requirements):
        """Give every article the same good scores, so the best-ranked wins."""
        scores = []
        for number in range(1, len(articles) + 1):
            scores.append(
                {
                    "number": number,
                    "relevance": 4,
                    "credibility": 4,
                    "novelty": 3,
                    "verifiable": True,
                }
            )
        return scores

    def write_post(self, article, requirements):
        """Return a headline, key points and a caption that credits the source."""
        headline = article.title[:MAX_HEADLINE_LENGTH]
        caption = (
            f"{article.text}\n\n"
            f"Source: {article.source_name}, {article.url}\n"
            "(Demo post: written from a template, not by an AI.)"
        )
        points = key_sentences(article.text)
        return {
            "headline": headline,
            "points": points,
            "figure": demo_figure(article),
            "quote": {},
            "takeaway": demo_takeaway(article, points),
            "caption": caption,
        }

    def correct_post(self, article, requirements, version, issues):
        """Return the caption with the source link added if it was missing."""
        caption = version.caption
        if article.url not in caption:
            caption = f"{caption}\n\nSource: {article.source_name}, {article.url}"
        return {
            "headline": version.headline,
            "points": version.points,
            "figure": version.figure,
            "quote": version.quote,
            "takeaway": version.takeaway,
            "caption": caption,
        }

    def write_image_prompt(self, article, headline):
        """Return a simple prompt that asks for artwork without words."""
        return (
            f"Abstract, colourful illustration about: {headline}. "
            "Bold shapes, no text, no letters, no logos."
        )

    def review_post(self, article, version):
        """Give fixed good scores, but flag a caption that hides its source."""
        caption = version.caption
        scores = {
            "grounding": 5,
            "relevance": 4,
            "clarity": 4,
            "tone": 5,
            "safety": 5,
            "shareability": 4,
        }
        issues = []
        if article.url not in caption:
            issues.append(
                {
                    "severity": "blocker",
                    "problem": "The caption does not link to its source.",
                    "fix_instruction": f"Add the source link: {article.url}",
                }
            )
        return {"scores": scores, "issues": issues}
