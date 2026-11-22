"""Turn a text model's answer into a post's content, checked against the article.

Some checks need no AI at all, so they are done here in plain code, every
time, for free:
- A quote must appear word for word in the article, or it is dropped.
- A figure must use numbers that appear in the article, or it is dropped.
- Text is shortened at a word boundary, never in the middle of a word.
- layout_issues() finds slides with too many words. Each becomes a "major"
  issue, which sends the post back for a rewrite (studio/verdicts.py).

The limits follow post_creation.md: a slide is read in about two seconds.
"""

import re

MAX_HEADLINE_LENGTH = 90
MAX_POINTS = 5
MAX_POINT_LENGTH = 220
MAX_TAKEAWAY_LENGTH = 200
# Openers post_creation.md forbids; removed even if the model uses them.
FILLER_OPENERS = ["quick tip:", "breaking:", "did you know:", "here's"]
# The prompt asks for fewer words; these leave a little room before a
# rewrite is demanded.
HEADLINE_WORD_LIMIT = 10
POINT_WORD_LIMIT = 32
TAKEAWAY_WORD_LIMIT = 25
FIGURE_VALUE_LIMIT = 14
# A quote shorter than this says too little to earn its own slide.
MIN_QUOTE_WORDS = 6
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*")
QUOTE_MARKS = {"“": '"', "”": '"', "‘": "'", "’": "'"}


def trim_words(text, max_length):
    """Return text cut to max_length at a word boundary, ending with "…"."""
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    cut = text[: max_length - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + "…"


def word_count(text):
    """Return the number of words in text."""
    return len(text.split())


def without_filler(headline):
    """Return the headline without a filler opener such as "Quick tip:"."""
    for opener in FILLER_OPENERS:
        if headline.lower().startswith(opener):
            return headline[len(opener) :].strip()
    return headline.strip()


def numbers_in(text):
    """Return the numbers written in text, without thousands commas."""
    numbers = []
    for found in NUMBER_PATTERN.findall(text):
        numbers.append(found.replace(",", ""))
    return numbers


def uses_article_numbers(text, article_numbers):
    """Return True if text has a number and every number is in the article."""
    numbers = numbers_in(text)
    if not numbers:
        return False
    for number in numbers:
        if number not in article_numbers:
            return False
    return True


def grounded_bars(bars, article_numbers):
    """Return the two comparison bars if both use the article's numbers."""
    if not bars or len(bars) != 2:
        return []
    kept = []
    for bar in bars:
        if not uses_article_numbers(bar["display"], article_numbers):
            return []
        kept.append(
            {
                "label": trim_words(bar["label"], 40),
                "amount": float(bar["amount"]),
                "display": bar["display"].strip(),
            }
        )
    return kept


def grounded_figure(figure, article_text):
    """Return the figure if its number is in the article, else {}."""
    if not figure:
        return {}
    article_numbers = numbers_in(article_text)
    if not uses_article_numbers(figure["value"], article_numbers):
        return {}
    return {
        "value": figure["value"].strip(),
        "label": trim_words(figure["label"], 140),
        "compare": grounded_bars(figure.get("compare"), article_numbers),
    }


def comparable(text):
    """Return text with plain quote marks, single spaces and lower case."""
    for curly, plain in QUOTE_MARKS.items():
        text = text.replace(curly, plain)
    return " ".join(text.split()).lower()


def grounded_quote(quote, article_text):
    """Return the quote if it is copied word for word from the article, else {}."""
    if not quote:
        return {}
    words = comparable(quote["text"]).strip("\"' ").rstrip(".,;:!?")
    article = comparable(article_text)
    if word_count(words) < MIN_QUOTE_WORDS or words not in article:
        return {}
    speaker = quote["speaker"].strip()
    name = comparable(speaker.split(",")[0])
    if name and name not in article:
        return {}
    return {"text": quote["text"].strip().strip('"“” '), "speaker": speaker}


def clean_points(points):
    """Return up to MAX_POINTS non-empty points, each shortened at a word."""
    cleaned = []
    for point in points[:MAX_POINTS]:
        if point.strip():
            cleaned.append(trim_words(point, MAX_POINT_LENGTH))
    return cleaned


def finished_post(result, article):
    """Return the post's content, checked against the article it came from."""
    caption = result["caption"]
    if article.url not in caption:
        caption = f"{caption}\n\nSource: {article.source_name}, {article.url}"
    article_text = f"{article.title}\n{article.text}"
    headline = without_filler(result["headline"])
    return {
        "headline": trim_words(headline, MAX_HEADLINE_LENGTH),
        "points": clean_points(result.get("points", [])),
        "figure": grounded_figure(result.get("figure"), article_text),
        "quote": grounded_quote(result.get("quote"), article_text),
        "takeaway": trim_words(result.get("takeaway") or "", MAX_TAKEAWAY_LENGTH),
        "caption": caption,
    }


def major_issue(problem, fix_instruction):
    """Return one issue that sends the post back for a rewrite."""
    return {
        "severity": "major",
        "problem": problem,
        "fix_instruction": fix_instruction,
    }


def layout_issues(version):
    """Return a major issue for each slide that holds too many words."""
    issues = []
    if word_count(version.headline) > HEADLINE_WORD_LIMIT:
        issues.append(
            major_issue(
                "The headline is too long to read at a glance on the cover.",
                "Rewrite the headline in 3 to 8 words.",
            )
        )
    for number, point in enumerate(version.points, start=1):
        if word_count(point) > POINT_WORD_LIMIT:
            issues.append(
                major_issue(
                    f"Key point {number} has {word_count(point)} words; its "
                    "slide becomes a wall of text.",
                    f"Rewrite key point {number} in 15 to 25 words.",
                )
            )
    issues = issues + figure_and_takeaway_issues(version)
    return issues


def figure_and_takeaway_issues(version):
    """Return major issues for a figure value or takeaway that is too long."""
    issues = []
    if len((version.figure or {}).get("value", "")) > FIGURE_VALUE_LIMIT:
        issues.append(
            major_issue(
                "The figure's value is too long to show as one big number.",
                "Make the figure value at most 12 characters, such as 50% or $2.1B.",
            )
        )
    if word_count(version.takeaway) > TAKEAWAY_WORD_LIMIT:
        issues.append(
            major_issue(
                "The takeaway is too long for the closing slide.",
                "Rewrite the takeaway in at most 20 words.",
            )
        )
    return issues
