"""The base class for a text model (the AI that writes and checks posts).

This is the adapter pattern: TextModel is the base class, and each provider
is one subclass (the demo one is in demo/text_model.py; real models through
LiteLLM arrive in Phase 3). studio.providers.get_text_model() picks the
right subclass for a user's saved credential.
"""


class TextModel:
    """The base class every text model follows."""

    def __init__(self, credential, api_key):
        self.credential = credential
        self.api_key = api_key

    def write_post(self, article, requirements):
        """Return {"headline": ..., "caption": ...} for a post about article.

        The caption must name the article's source and link to it.
        """
        raise NotImplementedError("Each text model must define write_post().")

    def write_image_prompt(self, article, headline):
        """Return a prompt for the image model. It asks for no written words."""
        raise NotImplementedError("Each text model must define write_image_prompt().")

    def review_post(self, article, headline, caption):
        """Return {"scores": {...}, "issues": [...]} for a written post.

        scores maps each check (grounding, relevance, clarity, tone, safety)
        to a number from 1 to 5. Each issue is a dict with severity ("minor"
        or "blocker"), problem and fix_instruction.
        """
        raise NotImplementedError("Each text model must define review_post().")
