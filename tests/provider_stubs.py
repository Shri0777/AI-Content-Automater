"""Routes that make the stub server answer like each real provider.

The answer shapes follow each provider's API reference: OpenAI-compatible
chat and images, Anthropic's Messages API, NVIDIA FLUX and fal.

The text "model" answers depend on which prompt it was sent, so a whole
post can be made through the stub, just like with a real model.
"""

import base64
import json
from io import BytesIO

from PIL import Image

from studio.prompts import (
    ARTICLE_SCORES_PROMPT,
    CORRECT_PROMPT,
    DRAFT_PROMPT,
    IMAGE_PROMPT_PROMPT,
    REVIEW_PROMPT,
)

OPENAI_CHAT_PATH = "/v1/chat/completions"
OPENAI_MODELS_PATH = "/v1/models"
OPENAI_IMAGES_PATH = "/v1/images/generations"
ANTHROPIC_MESSAGES_PATH = "/v1/messages"
NVIDIA_MODEL = "black-forest-labs/flux.1-dev"
FAL_MODEL = "fal-ai/flux/schnell"


def image_base64(image_format):
    """Return a small real image (PNG or JPEG) as base64 text."""
    buffer = BytesIO()
    Image.new("RGB", (64, 64), "teal").save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode()


def reply_for(system_prompt):
    """Return the JSON text a well-behaved model would reply with."""
    if system_prompt in [DRAFT_PROMPT["system"], CORRECT_PROMPT["system"]]:
        answer = {
            "headline": "Stub model headline",
            "caption": "A summary written by the stub model.",
        }
    elif system_prompt == IMAGE_PROMPT_PROMPT["system"]:
        answer = {"prompt": "Teal waves under a soft light, no text."}
    elif system_prompt == ARTICLE_SCORES_PROMPT["system"]:
        score = {
            "number": 1,
            "relevance": 5,
            "credibility": 4,
            "novelty": 4,
            "verifiable": True,
        }
        answer = {"scores": [score]}
    elif system_prompt == REVIEW_PROMPT["system"]:
        scores = {"grounding": 5, "relevance": 5, "clarity": 4, "tone": 5, "safety": 5}
        answer = {"scores": scores, "issues": []}
    else:
        return "OK"
    return json.dumps(answer)


def openai_chat(body):
    """Answer a /chat/completions request."""
    reply = reply_for(body["messages"][0]["content"])
    return {
        "json": {
            "choices": [{"message": {"role": "assistant", "content": reply}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 40},
        }
    }


def anthropic_messages(body):
    """Answer a Messages API request."""
    return {
        "json": {
            "id": "msg_stub",
            "type": "message",
            "role": "assistant",
            "model": body["model"],
            "content": [{"type": "text", "text": reply_for(body.get("system", ""))}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 120, "output_tokens": 40},
        }
    }


def add_provider_routes(stub):
    """Make the stub answer every provider's requests successfully."""
    stub.set_route("POST", OPENAI_CHAT_PATH, openai_chat)
    stub.set_route("GET", OPENAI_MODELS_PATH, {"json": {"data": []}})
    stub.set_route(
        "POST",
        OPENAI_IMAGES_PATH,
        {"json": {"data": [{"b64_json": image_base64("PNG")}]}},
    )
    stub.set_route("POST", ANTHROPIC_MESSAGES_PATH, anthropic_messages)
    stub.set_route(
        "GET",
        "/v1/models/claude-opus-5-5",
        {"json": {"type": "model", "id": "claude-opus-5-5", "display_name": "Opus"}},
    )
    nvidia_artifact = {"base64": image_base64("JPEG"), "finishReason": "SUCCESS"}
    stub.set_route(
        "POST", f"/{NVIDIA_MODEL}", {"json": {"artifacts": [nvidia_artifact]}}
    )
    fal_image = {"url": "data:image/png;base64," + image_base64("PNG")}
    stub.set_route("POST", f"/{FAL_MODEL}", {"json": {"images": [fal_image]}})


def credential_details(stub, adapter):
    """Return save_credential() details that point adapter at the stub."""
    details = {
        "openai_compatible": ("gpt-stub", f"{stub.base_url}/v1"),
        "anthropic": ("claude-opus-5-5", stub.base_url),
        "nvidia_flux": (NVIDIA_MODEL, stub.base_url),
        "fal": (FAL_MODEL, stub.base_url),
    }
    model_name, base_url = details[adapter]
    return {
        "adapter": adapter,
        "model_name": model_name,
        "base_url": base_url,
        "api_key": "sk-stub-secret-key-0042",
    }
