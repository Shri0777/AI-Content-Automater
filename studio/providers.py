"""Find the text or image model that matches a user's saved credential."""

from credentials.services import read_api_key
from demo.image_model import DemoImageModel
from demo.text_model import DemoTextModel
from studio.anthropic_text import AnthropicTextModel
from studio.image_providers import FalImageModel, NvidiaFluxImageModel
from studio.openai_compatible import (
    OpenAICompatibleImageModel,
    OpenAICompatibleTextModel,
)

# Which class handles each "adapter" name saved on a credential. These must
# match credentials.models.ADAPTERS_BY_KIND (a test checks that they do).
TEXT_MODEL_CLASSES = {
    "demo": DemoTextModel,
    "openai_compatible": OpenAICompatibleTextModel,
    "anthropic": AnthropicTextModel,
}
IMAGE_MODEL_CLASSES = {
    "demo": DemoImageModel,
    "openai_compatible": OpenAICompatibleImageModel,
    "nvidia_flux": NvidiaFluxImageModel,
    "fal": FalImageModel,
}


def get_text_model(credential):
    """Return a ready-to-use text model for a "text" credential."""
    model_class = TEXT_MODEL_CLASSES[credential.adapter]
    return model_class(credential, read_api_key(credential))


def get_image_model(credential):
    """Return a ready-to-use image model for an "image" credential."""
    model_class = IMAGE_MODEL_CLASSES[credential.adapter]
    return model_class(credential, read_api_key(credential))


def get_provider(credential):
    """Return the model for a credential of any kind, or None for news.

    The shared news sources need no key; a user's own news key (an optional
    extra, added later) cannot be checked yet.
    """
    if credential.kind == "text":
        return get_text_model(credential)
    if credential.kind == "image":
        return get_image_model(credential)
    return None
