"""Tests for making a whole post with real provider adapters.

The adapters talk over HTTP to the stub server, which answers like the real
services. Background jobs run straight away in tests.
"""

import logging

import pytest

from credentials.models import ProviderCredential
from credentials.services import save_credential
from notifications.models import Notification
from studio import tasks
from studio.models import Post
from tests.provider_stubs import (
    ANTHROPIC_MESSAGES_PATH,
    FAL_MODEL,
    add_provider_routes,
    anthropic_messages,
    credential_details,
)

SECRET = "sk-stub-secret-key-0042"


@pytest.fixture
def real_providers(user, stub_server):
    """Point the user's text and image keys at Claude and fal on the stub."""
    add_provider_routes(stub_server)
    for kind, adapter in [("text", "anthropic"), ("image", "fal")]:
        details = credential_details(stub_server, adapter)
        details["kind"] = kind
        save_credential(user, details)
    return stub_server


def generate(client, plan):
    """Ask for a post now and return the post's details."""
    post_id = client.post(f"/api/v1/plans/{plan.id}/generate-now/").json()["id"]
    return client.get(f"/api/v1/posts/{post_id}/").json()


def test_a_post_is_made_with_real_providers(client, plan, real_providers):
    post = generate(client, plan)

    assert post["status"] == "awaiting_approval"
    assert post["versions"][0]["headline"] == "Stub model headline"
    assert post["article"]["url"] in post["versions"][0]["caption"]
    assert len(real_providers.requests_to(f"/{FAL_MODEL}")) == 1


def test_each_step_records_its_models_prompts_and_tokens(client, plan, real_providers):
    steps = generate(client, plan)["steps"]

    imaging = steps[2]
    assert imaging["providers"] == (f"anthropic:claude-opus-5-5, fal:{FAL_MODEL}")
    assert imaging["prompt_versions"] == "image-prompt-v1"
    assert imaging["input_tokens"] == 120
    assert steps[0]["providers"] == ""


def test_a_busy_provider_is_tried_again(client, plan, real_providers):
    answers = [{"status": 429, "json": {}}]

    def busy_once(body):
        if answers:
            return answers.pop(0)
        return anthropic_messages(body)

    real_providers.set_route("POST", ANTHROPIC_MESSAGES_PATH, busy_once)

    post = generate(client, plan)

    assert post["status"] == "awaiting_approval"
    drafting = [step for step in post["steps"] if step["stage"] == "drafting"]
    assert [step["succeeded"] for step in drafting] == [False, True]


def test_a_provider_that_stays_busy_fails_the_post_in_the_end(
    client, plan, real_providers
):
    real_providers.set_route(
        "POST", ANTHROPIC_MESSAGES_PATH, {"status": 529, "json": {}}
    )

    post = generate(client, plan)

    assert post["status"] == "failed"
    assert "busy" in post["status_reason"]
    drafting = [step for step in post["steps"] if step["stage"] == "drafting"]
    assert len(drafting) == tasks.MAX_RETRIES + 1


def test_a_rejected_key_marks_the_credential_and_tells_the_user(
    client, user, plan, real_providers
):
    real_providers.set_route(
        "POST", ANTHROPIC_MESSAGES_PATH, {"status": 401, "json": {}}
    )

    post = generate(client, plan)

    assert post["status"] == "failed"
    text_key = ProviderCredential.objects.get(user=user, kind="text")
    assert text_key.status == "invalid"
    assert Notification.objects.filter(user=user, kind="credential_invalid").exists()
    drafting = [step for step in post["steps"] if step["stage"] == "drafting"]
    assert len(drafting) == 1


def test_the_api_key_never_appears_in_responses_or_logs(
    client, plan, real_providers, caplog
):
    caplog.set_level(logging.DEBUG)

    post_id = generate(client, plan)["id"]
    responses = [
        client.get("/api/v1/credentials/").content,
        client.get(f"/api/v1/posts/{post_id}/").content,
        client.post(f"/api/v1/posts/{post_id}/approve/").content,
    ]
    for credential in ProviderCredential.objects.all():
        responses.append(
            client.post(f"/api/v1/credentials/{credential.id}/test/").content
        )

    for content in responses:
        assert SECRET not in content.decode()
    assert SECRET not in caplog.text
    assert len(caplog.records) > 0
    assert Post.objects.get().status == "published"
