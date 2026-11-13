"""Contract tests: every text and image provider behaves the same way.

The demo fakes and the real adapters (talking over HTTP to the stub server)
pass the same checks, so demo mode and real providers cannot drift apart.
"""

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from PIL import Image

from core.errors import ProviderBusy, ProviderError, ProviderKeyRejected
from credentials.models import ADAPTERS_BY_KIND
from credentials.services import save_credential
from newsroom.models import Article
from studio.providers import (
    IMAGE_MODEL_CLASSES,
    TEXT_MODEL_CLASSES,
    get_image_model,
    get_text_model,
)
from tests.provider_stubs import (
    ANTHROPIC_MESSAGES_PATH,
    FAL_MODEL,
    NVIDIA_MODEL,
    OPENAI_CHAT_PATH,
    add_provider_routes,
    credential_details,
)

TEXT_ADAPTERS = ["demo", "openai_compatible", "anthropic"]
IMAGE_ADAPTERS = ["demo", "openai_compatible", "nvidia_flux", "fal"]


@pytest.fixture
def user(db):
    """A saved user."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


@pytest.fixture
def article(db):
    """A saved article to write about."""
    return Article.objects.create(
        url_hash="a1",
        url="https://example.com/story",
        title="A test story",
        source_name="Example News",
        preset="ai_news",
        published_at="2026-11-13T09:00:00Z",
        text="Something happened today.",
    )


def make_credential(user, stub_server, kind, adapter):
    """Save a credential of kind that points adapter at the stub server."""
    add_provider_routes(stub_server)
    details = {"kind": kind, "adapter": "demo"}
    if adapter != "demo":
        details = credential_details(stub_server, adapter)
        details["kind"] = kind
    return save_credential(user, details)


def test_every_adapter_the_api_accepts_has_a_provider_class():
    assert sorted(ADAPTERS_BY_KIND["text"]) == sorted(TEXT_MODEL_CLASSES)
    assert sorted(ADAPTERS_BY_KIND["image"]) == sorted(IMAGE_MODEL_CLASSES)


@pytest.mark.parametrize("adapter", TEXT_ADAPTERS)
def test_every_text_model_writes_a_post_that_credits_its_source(
    user, article, stub_server, adapter
):
    model = get_text_model(make_credential(user, stub_server, "text", adapter))

    post = model.write_post(article, "Short and friendly.")
    prompt = model.write_image_prompt(article, post["headline"])
    review = model.review_post(article, post["headline"], post["caption"])

    assert post["headline"]
    assert article.url in post["caption"]
    assert prompt
    assert set(review["scores"]) == {
        "grounding",
        "relevance",
        "clarity",
        "tone",
        "safety",
    }
    assert isinstance(review["issues"], list)
    model.check_connection()


@pytest.mark.parametrize("adapter", IMAGE_ADAPTERS)
def test_every_image_model_returns_a_real_image(user, stub_server, adapter):
    model = get_image_model(make_credential(user, stub_server, "image", adapter))

    artwork = model.make_artwork("Teal waves", 1080, 1080)

    Image.open(BytesIO(artwork)).verify()
    model.check_connection()


@pytest.mark.parametrize("adapter", ["openai_compatible", "anthropic"])
def test_real_text_models_count_tokens_and_prompt_versions(
    user, article, stub_server, adapter
):
    model = get_text_model(make_credential(user, stub_server, "text", adapter))

    model.write_post(article, "")

    assert model.input_tokens == 120
    assert model.output_tokens == 40
    assert model.prompt_versions == ["draft-v1"]


def test_the_users_own_key_is_sent_to_the_provider(user, stub_server):
    model = get_text_model(make_credential(user, stub_server, "text", "anthropic"))

    model.check_connection()

    # The official library chooses the header (anthropic 2.x sends a Bearer
    # token); what matters is that it is this user's key.
    headers = stub_server.requests[-1]["headers"]
    sent_keys = [headers.get("x-api-key"), headers.get("Authorization")]
    assert "sk-stub-secret-key-0042" in str(sent_keys)


TEXT_ENDPOINTS = [
    ("openai_compatible", OPENAI_CHAT_PATH),
    ("anthropic", ANTHROPIC_MESSAGES_PATH),
]
FAILURES = [(401, ProviderKeyRejected), (429, ProviderBusy), (500, ProviderBusy)]


@pytest.mark.parametrize("endpoint", TEXT_ENDPOINTS)
@pytest.mark.parametrize("failure", FAILURES)
def test_text_provider_failures_become_our_error_kinds(
    user, article, stub_server, endpoint, failure
):
    adapter, path = endpoint
    status, error_class = failure
    credential = make_credential(user, stub_server, "text", adapter)
    stub_server.set_route("POST", path, {"status": status, "json": {}})

    with pytest.raises(error_class) as error:
        get_text_model(credential).write_post(article, "")

    if error_class is ProviderKeyRejected:
        assert error.value.credential == credential


def test_a_model_that_answers_badly_once_is_asked_to_fix_it(user, article, stub_server):
    credential = make_credential(user, stub_server, "text", "openai_compatible")
    answers = ["Sure! Here is your post.", '{"headline": "Fixed", "caption": "Done."}']

    def bad_then_good(body):
        reply = answers.pop(0)
        return {"json": {"choices": [{"message": {"content": reply}}]}}

    stub_server.set_route("POST", OPENAI_CHAT_PATH, bad_then_good)

    post = get_text_model(credential).write_post(article, "")

    assert post["headline"] == "Fixed"
    second_request = stub_server.requests_to(OPENAI_CHAT_PATH)[1]["body"]
    assert "could not be used" in second_request["messages"][-1]["content"]


def test_a_model_that_never_answers_properly_fails_clearly(user, article, stub_server):
    credential = make_credential(user, stub_server, "text", "openai_compatible")
    nonsense = {"json": {"choices": [{"message": {"content": '{"wrong": 1}'}}]}}
    stub_server.set_route("POST", OPENAI_CHAT_PATH, nonsense)

    with pytest.raises(ProviderError, match="usable answer"):
        get_text_model(credential).write_post(article, "")
    assert len(stub_server.requests_to(OPENAI_CHAT_PATH)) == 2


def test_a_claude_refusal_is_a_clear_error(user, article, stub_server):
    credential = make_credential(user, stub_server, "text", "anthropic")
    refusal = {
        "json": {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [],
            "stop_reason": "refusal",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 0},
        }
    }
    stub_server.set_route("POST", ANTHROPIC_MESSAGES_PATH, refusal)

    with pytest.raises(ProviderError, match="declined"):
        get_text_model(credential).write_post(article, "")


def test_claude_is_never_called_without_the_users_own_key(user, stub_server):
    credential = make_credential(user, stub_server, "text", "anthropic")
    credential.encrypted_key = ""

    with pytest.raises(ProviderKeyRejected):
        get_text_model(credential).check_connection()
    assert stub_server.requests == []


def test_nvidia_reports_its_safety_filter(user, stub_server):
    credential = make_credential(user, stub_server, "image", "nvidia_flux")
    filtered = {"artifacts": [{"base64": "", "finishReason": "CONTENT_FILTERED"}]}
    stub_server.set_route("POST", f"/{NVIDIA_MODEL}", {"json": filtered})

    with pytest.raises(ProviderError, match="safety filter"):
        get_image_model(credential).make_artwork("prompt", 1080, 1080)


def test_fal_images_given_as_a_link_are_downloaded(user, stub_server):
    credential = make_credential(user, stub_server, "image", "fal")
    png_route = {"body": b"not checked here", "content_type": "image/png"}
    stub_server.set_route("GET", "/files/art.png", png_route)
    linked = {"images": [{"url": f"{stub_server.base_url}/files/art.png"}]}
    stub_server.set_route("POST", f"/{FAL_MODEL}", {"json": linked})

    assert get_image_model(credential).make_artwork("p", 1080, 1080) == (
        b"not checked here"
    )
