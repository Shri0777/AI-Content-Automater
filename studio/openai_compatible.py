"""Text and image models for any service that speaks OpenAI's API format.

Many services accept the same requests as OpenAI: OpenAI itself,
OpenRouter, Groq, Mistral, DeepSeek, Together, Google Gemini's compatible
endpoint, NVIDIA NIM, and model servers you run yourself (Ollama, vLLM).
The user picks the service with base_url and the model with model_name.

Requests go through core/web.py, which applies our safety rules.
"""

import base64

from core import web
from core.errors import ProviderError
from studio.image_models import ImageModel
from studio.text_models import TextModel

DEFAULT_BASE_URL = "https://api.openai.com/v1"
# Square artwork; the poster renderer crops and scales it to the poster.
IMAGE_SIZE = "1024x1024"


def api_address(credential, path):
    """Return the full address of path on the credential's service."""
    base_url = credential.base_url or DEFAULT_BASE_URL
    return base_url.rstrip("/") + path


def auth_headers(api_key):
    """Return the request headers that carry the API key (if there is one)."""
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


class OpenAICompatibleTextModel(TextModel):
    """A chat model reached through the /chat/completions endpoint."""

    def ask(self, system, messages):
        """Send the conversation and return the model's reply text."""
        body = {
            "model": self.credential.model_name,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        answer = web.post_json(
            api_address(self.credential, "/chat/completions"),
            auth_headers(self.api_key),
            body,
        )
        try:
            text = answer["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("The model's answer had an unexpected shape.") from None
        usage = answer.get("usage") or {}
        self.input_tokens = self.input_tokens + usage.get("prompt_tokens", 0)
        self.output_tokens = self.output_tokens + usage.get("completion_tokens", 0)
        return text or ""

    def check_connection(self):
        """Send a one-line request, which proves the key and model name work."""
        self.ask("Reply with the word OK.", [{"role": "user", "content": "Ping"}])


class OpenAICompatibleImageModel(ImageModel):
    """An image model reached through the /images/generations endpoint."""

    def draw(self, prompt, width, height):
        """Return image bytes; the service sends them as base64 or as a link."""
        body = {
            "model": self.credential.model_name,
            "prompt": prompt,
            "size": IMAGE_SIZE,
            "n": 1,
        }
        answer = web.post_json(
            api_address(self.credential, "/images/generations"),
            auth_headers(self.api_key),
            body,
        )
        try:
            image = answer["data"][0]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("The image answer had an unexpected shape.") from None
        if image.get("b64_json"):
            return base64.b64decode(image["b64_json"])
        if image.get("url"):
            return web.get_bytes(image["url"])
        raise ProviderError("The image answer contained no image.")

    def check_connection(self):
        """List the service's models: free, and proves the key works."""
        web.get_json(
            api_address(self.credential, "/models"), auth_headers(self.api_key)
        )
