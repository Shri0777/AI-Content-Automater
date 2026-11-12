"""Find the text or image model that matches a user's saved credential."""

from credentials.services import read_api_key
from demo.image_model import DemoImageModel
from demo.text_model import DemoTextModel

# Which class handles each "adapter" name saved on a credential. Real
# providers are added here in Phase 3.
TEXT_MODEL_CLASSES = {"demo": DemoTextModel}
IMAGE_MODEL_CLASSES = {"demo": DemoImageModel}


def get_text_model(credential):
    """Return a ready-to-use text model for a "text" credential."""
    model_class = TEXT_MODEL_CLASSES[credential.adapter]
    return model_class(credential, read_api_key(credential))


def get_image_model(credential):
    """Return a ready-to-use image model for an "image" credential."""
    model_class = IMAGE_MODEL_CLASSES[credential.adapter]
    return model_class(credential, read_api_key(credential))
