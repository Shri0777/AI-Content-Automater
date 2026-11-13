"""The base class for an image model (the AI that makes poster artwork).

This is the adapter pattern. Each provider is one subclass that only knows
how to turn a prompt into image bytes: its draw() method. Providers:
openai_compatible.py, image_providers.py (NVIDIA FLUX and fal) and
demo/image_model.py. studio.providers.get_image_model() picks one.
"""

from core.errors import ProviderKeyRejected


class ImageModel:
    """The base class every image model follows."""

    def __init__(self, credential, api_key):
        self.credential = credential
        self.api_key = api_key
        # Image models are not charged per token; kept for the same records.
        self.input_tokens = 0
        self.output_tokens = 0
        self.prompt_versions = []

    def draw(self, prompt, width, height):
        """Return image bytes (PNG or JPEG) of artwork for prompt.

        The provider may return a different size; studio/posters.py crops
        and scales it to the poster. Raise ProviderError on failure.
        """
        raise NotImplementedError("Each image model must define draw().")

    def check_connection(self):
        """Make a request that proves the key works."""
        raise NotImplementedError("Each image model must define check_connection().")

    def describe(self):
        """Return the provider and model, for example "fal:fal-ai/flux/schnell"."""
        return f"{self.credential.adapter}:{self.credential.model_name}"

    def make_artwork(self, prompt, width, height):
        """Return artwork bytes; a rejected key notes which credential it was.

        The artwork has no words: the headline is added later by
        studio/posters.py, so it is always spelled correctly.
        """
        try:
            return self.draw(prompt, width, height)
        except ProviderKeyRejected as error:
            error.credential = self.credential
            raise
