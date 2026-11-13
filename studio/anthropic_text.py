"""Text models from Anthropic (Claude), through Anthropic's official library.

This is the only file that uses the "anthropic" library. Its errors are
turned into our own three kinds (core/errors.py), so the rest of the code
never needs to know about them.

Model names look like "claude-opus-5-5" or "claude-sonnet-5-5".
"""

import anthropic

from core import web
from core.errors import ProviderBusy, ProviderError, ProviderKeyRejected
from studio.text_models import TextModel

MAX_TOKENS = 16000
TIMEOUT_SECONDS = 120
# These models can hand a declined request to another model on Anthropic's
# side ("server-side fallbacks"), so a refusal does not end the request.
FALLBACK_MODELS = [
    "claude-fable-5-2",
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
]
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def translate_error(error):
    """Return our own error for one of the anthropic library's errors."""
    if isinstance(
        error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)
    ):
        return ProviderKeyRejected("Anthropic refused the API key. Check the key.")
    if isinstance(error, (anthropic.RateLimitError, anthropic.InternalServerError)):
        return ProviderBusy("Anthropic is busy right now.")
    if isinstance(error, anthropic.APIConnectionError):
        return ProviderBusy("Anthropic could not be reached.")
    if isinstance(error, anthropic.APIStatusError):
        return ProviderError(
            f"Anthropic refused the request (HTTP {error.status_code}): "
            f"{error.message[:300]}"
        )
    return ProviderError("The request to Anthropic failed.")


class AnthropicTextModel(TextModel):
    """A Claude model reached through the Messages API."""

    def make_client(self):
        """Return a client that only ever uses this credential's own key."""
        # Without an explicit key the library would look for one on the
        # server (environment variables, saved logins), which could be the
        # operator's own key. So a missing key is refused here.
        if not self.api_key:
            raise ProviderKeyRejected("Add your Anthropic API key to use Claude.")
        base_url = None
        if self.credential.base_url:
            web.check_address(self.credential.base_url)
            base_url = self.credential.base_url
        return anthropic.Anthropic(
            api_key=self.api_key,
            base_url=base_url,
            timeout=TIMEOUT_SECONDS,
            # Our background jobs retry busy providers themselves.
            max_retries=0,
        )

    def send_messages(self, system, messages):
        """Send one request and return Anthropic's response object."""
        client = self.make_client()
        model = self.credential.model_name
        if model in FALLBACK_MODELS:
            return client.beta.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        return client.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=system, messages=messages
        )

    def ask(self, system, messages):
        """Send the conversation and return Claude's reply text."""
        try:
            response = self.send_messages(system, messages)
        except anthropic.APIError as error:
            raise translate_error(error) from None
        self.input_tokens = self.input_tokens + response.usage.input_tokens
        self.output_tokens = self.output_tokens + response.usage.output_tokens
        if response.stop_reason == "refusal":
            raise ProviderError("The model declined to write about this article.")
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "".join(text_parts)

    def check_connection(self):
        """Look the model up: free, and proves the key and model name work."""
        try:
            self.make_client().models.retrieve(self.credential.model_name)
        except anthropic.APIError as error:
            raise translate_error(error) from None
