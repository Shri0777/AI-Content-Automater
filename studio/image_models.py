"""The base class for an image model (the AI that makes poster artwork).

This is the adapter pattern: ImageModel is the base class, and each provider
is one subclass (the demo one is in demo/image_model.py; real providers
arrive in Phase 3). studio.providers.get_image_model() picks the right
subclass for a user's saved credential.
"""


class ImageModel:
    """The base class every image model follows."""

    def __init__(self, credential, api_key):
        self.credential = credential
        self.api_key = api_key

    def make_artwork(self, prompt, width, height):
        """Return PNG image bytes of artwork for prompt, width x height pixels.

        The artwork has no words: the headline is added later by
        studio/posters.py, so it is always spelled correctly.
        """
        raise NotImplementedError("Each image model must define make_artwork().")
