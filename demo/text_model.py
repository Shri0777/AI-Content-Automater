"""A fake text model for demo mode and tests.

It fills in templates instead of calling an AI, so its answers are always
the same for the same article. Posts it writes are canned, not AI output.
"""

from studio.text_models import TextModel

MAX_HEADLINE_LENGTH = 90


class DemoTextModel(TextModel):
    """Writes and reviews posts from templates, without any AI."""

    def write_post(self, article, requirements):
        """Return a headline and a caption that credits the source."""
        headline = article.title[:MAX_HEADLINE_LENGTH]
        caption = (
            f"{article.text}\n\n"
            f"Source: {article.source_name}, {article.url}\n"
            "(Demo post: written from a template, not by an AI.)"
        )
        return {"headline": headline, "caption": caption}

    def write_image_prompt(self, article, headline):
        """Return a simple prompt that asks for artwork without words."""
        return (
            f"Abstract, colourful illustration about: {headline}. "
            "Bold shapes, no text, no letters, no logos."
        )

    def review_post(self, article, headline, caption):
        """Give fixed good scores, but flag a caption that hides its source."""
        scores = {
            "grounding": 5,
            "relevance": 4,
            "clarity": 4,
            "tone": 5,
            "safety": 5,
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
