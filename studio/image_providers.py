"""Image models from NVIDIA (FLUX) and fal.

Both are reached through core/web.py, which applies our safety rules. Their
request and answer formats come from each provider's API reference; each
has a contract test against a stub server (studio/tests).

Neither offers a free way to check a key, so check_connection() makes the
smallest real image. That may cost the user a fraction of a cent.
"""

import base64

from core import web
from core.errors import ProviderError, ProviderNotFound
from studio.image_models import ImageModel

NVIDIA_BASE_URL = "https://ai.api.nvidia.com/v1/genai"
FAL_BASE_URL = "https://fal.run"
# Both providers make square artwork; the poster renderer crops and scales.
ARTWORK_SIDE = 1024
# NVIDIA's fewest allowed steps: fastest and cheapest, used to check a key.
NVIDIA_CHECK_STEPS = 5


def decode_base64(text):
    """Return the bytes in a base64 text, or raise ProviderError."""
    try:
        return base64.b64decode(text, validate=True)
    except (TypeError, ValueError):
        raise ProviderError("The image answer could not be read.") from None


def unknown_nvidia_model(model_name):
    """Explain a model name NVIDIA does not know, suggesting the likely ID.

    The model's web page (build.nvidia.com/black-forest-labs/flux_1-dev) is
    not its API ID (black-forest-labs/flux.1-dev), so a name copied from the
    address bar is turned into a suggestion. It is only suggested, never used.
    """
    message = (
        f"NVIDIA has no model at '{model_name}'. Enter the API's model ID, "
        "for example black-forest-labs/flux.1-dev (not the web page address "
        "and not the name of your API key)."
    )
    guess = model_name.strip().replace("_1-", ".1-")
    if "/" not in guess:
        guess = "black-forest-labs/" + guess
    if "flux" in guess.lower() and guess != model_name:
        message = f"{message} Did you mean {guess}?"
    return message


class NvidiaFluxImageModel(ImageModel):
    """FLUX models on NVIDIA's API, such as "black-forest-labs/flux.1-dev"."""

    def generate(self, prompt, steps=None):
        """Ask NVIDIA for one image and return its bytes (JPEG)."""
        base_url = self.credential.base_url or NVIDIA_BASE_URL
        body = {
            "prompt": prompt,
            "mode": "base",
            "width": ARTWORK_SIDE,
            "height": ARTWORK_SIDE,
        }
        if steps is not None:
            body["steps"] = steps
        answer = self.ask(base_url, body)
        try:
            artifact = answer["artifacts"][0]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("The image answer had an unexpected shape.") from None
        if artifact.get("finishReason") == "CONTENT_FILTERED":
            raise ProviderError("NVIDIA's safety filter blocked this image prompt.")
        if artifact.get("finishReason") != "SUCCESS":
            raise ProviderError("NVIDIA could not make the image.")
        return decode_base64(artifact.get("base64"))

    def ask(self, base_url, body):
        """Send the image request; explain a wrong model path (HTTP 404)."""
        try:
            return web.post_json(
                f"{base_url.rstrip('/')}/{self.credential.model_name}",
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                body,
            )
        except ProviderNotFound:
            raise ProviderError(
                unknown_nvidia_model(self.credential.model_name)
            ) from None

    def draw(self, prompt, width, height):
        """Return square artwork for prompt."""
        return self.generate(prompt)

    def check_connection(self):
        """Make one quick, low-quality image to prove the key works."""
        self.generate("A plain blue square.", steps=NVIDIA_CHECK_STEPS)


class FalImageModel(ImageModel):
    """Models hosted on fal, such as "fal-ai/flux/schnell"."""

    def draw(self, prompt, width, height):
        """Return square PNG artwork for prompt."""
        base_url = self.credential.base_url or FAL_BASE_URL
        body = {
            "prompt": prompt,
            "image_size": {"width": ARTWORK_SIDE, "height": ARTWORK_SIDE},
            "num_images": 1,
            "output_format": "png",
            # The image comes back inside the answer, not as a link to fetch.
            "sync_mode": True,
        }
        answer = web.post_json(
            f"{base_url.rstrip('/')}/{self.credential.model_name}",
            {"Authorization": f"Key {self.api_key}"},
            body,
        )
        try:
            image_address = answer["images"][0]["url"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("The image answer had an unexpected shape.") from None
        if image_address.startswith("data:"):
            return decode_base64(image_address.split(",", 1)[-1])
        return web.get_bytes(image_address)

    def check_connection(self):
        """Make one small image to prove the key works."""
        self.draw("A plain blue square.", ARTWORK_SIDE, ARTWORK_SIDE)
