"""A fake image model for demo mode and tests.

It draws simple gradient-and-circle artwork instead of calling an AI, so the
real poster renderer still runs on a real image.
"""

from studio.image_models import ImageModel
from studio.posters import draw_abstract_artwork


class DemoImageModel(ImageModel):
    """Makes abstract artwork that depends only on the prompt."""

    def make_artwork(self, prompt, width, height):
        """Return PNG bytes of artwork for prompt."""
        return draw_abstract_artwork(prompt, width, height)
