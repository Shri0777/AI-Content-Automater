"""Provider errors tell the user what to fix, in plain words.

A wrong model name is the commonest setup mistake, so these answers are
replayed from what Anthropic and NVIDIA really send for one.
"""

import pytest
from django.contrib.auth import get_user_model

from core.errors import ProviderError
from credentials.services import save_credential
from studio.providers import get_image_model, get_text_model
from tests.provider_stubs import add_provider_routes, credential_details


@pytest.fixture
def user(db):
    """A saved user."""
    return get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )


def make_credential(user, stub_server, kind, adapter):
    """Save a credential of kind that points adapter at the stub server."""
    add_provider_routes(stub_server)
    details = credential_details(stub_server, adapter)
    details["kind"] = kind
    return save_credential(user, details)


def test_an_unknown_claude_model_is_explained_with_anthropics_suggestion(
    user, stub_server
):
    # What Anthropic answers for "claude-sonnet-5.5" (a dot instead of a dash).
    credential = make_credential(user, stub_server, "text", "anthropic")
    not_found = {
        "type": "error",
        "error": {
            "type": "not_found_error",
            "message": "model: claude-sonnet-5.5 was not found. "
            "Did you mean claude-sonnet-5-5?",
        },
        "request_id": "req_0123",
    }
    credential.model_name = "claude-sonnet-5.5"
    stub_server.set_route(
        "GET", "/v1/models/claude-sonnet-5.5", {"status": 404, "json": not_found}
    )

    with pytest.raises(ProviderError) as raised:
        get_text_model(credential).check_connection()

    message = str(raised.value)
    assert "Did you mean claude-sonnet-5-5?" in message
    assert "request_id" not in message
    assert "{" not in message


def test_an_unknown_nvidia_model_path_is_explained(user, stub_server):
    # NVIDIA answers 404 when the model is not a path like the example.
    credential = make_credential(user, stub_server, "image", "nvidia_flux")
    credential.model_name = "NVIDIABuild-Autogen-72"

    with pytest.raises(ProviderError) as raised:
        get_image_model(credential).check_connection()

    message = str(raised.value)
    assert "NVIDIABuild-Autogen-72" in message
    assert "black-forest-labs/flux.1-dev" in message


def test_a_model_copied_from_nvidias_web_address_gets_the_api_id_suggested(
    user, stub_server
):
    # build.nvidia.com/black-forest-labs/flux_1-dev is the web page; the API
    # wants black-forest-labs/flux.1-dev. The fix is suggested, not applied.
    credential = make_credential(user, stub_server, "image", "nvidia_flux")
    credential.model_name = "flux_1-dev"

    with pytest.raises(ProviderError) as raised:
        get_image_model(credential).check_connection()

    assert "Did you mean black-forest-labs/flux.1-dev?" in str(raised.value)
    assert credential.model_name == "flux_1-dev"
