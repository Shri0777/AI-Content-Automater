"""What credential data goes into and comes out of the API."""

import re

from django.conf import settings
from rest_framework import serializers

from core.web import UnsafeAddress, check_url_format
from credentials.models import (
    ADAPTERS_BY_KIND,
    KEY_REQUIRED_ADAPTERS,
    KIND_CHOICES,
    ProviderCredential,
)

# Model names such as "gpt-4o-mini", "claude-opus-5-5" or
# "black-forest-labs/flux.1-dev". Some providers put the name in the web
# address, so only these characters are allowed.
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$")


def check_adapter(data):
    """Return an error message about the chosen provider, or ""."""
    allowed_adapters = ADAPTERS_BY_KIND[data["kind"]]
    if data["adapter"] not in allowed_adapters:
        return f"Choose one of: {', '.join(allowed_adapters)}."
    if data["adapter"] == "demo" and not settings.DEMO_MODE:
        return "Demo providers only work when DEMO_MODE is on."
    return ""


def check_model_name(data):
    """Return an error message about the model name, or ""."""
    model_name = data.get("model_name", "")
    if data["adapter"] == "demo":
        return ""
    if not model_name:
        return "Enter the model's name, for example claude-opus-5-5."
    if not MODEL_NAME_PATTERN.match(model_name) or ".." in model_name:
        return "Use only letters, numbers and . _ : / @ - in the model name."
    return ""


def check_base_url(data):
    """Return an error message about the custom address, or ""."""
    if not data.get("base_url"):
        return ""
    try:
        check_url_format(data["base_url"])
    except UnsafeAddress as error:
        return str(error)
    return ""


class CredentialSerializer(serializers.ModelSerializer):
    """A saved credential. The API key is accepted but never sent back."""

    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=KIND_CHOICES)

    class Meta:
        model = ProviderCredential
        fields = [
            "id",
            "kind",
            "adapter",
            "model_name",
            "base_url",
            "api_key",
            "key_hint",
            "status",
            "last_checked_at",
            "last_error",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "key_hint",
            "status",
            "last_checked_at",
            "last_error",
            "updated_at",
        ]
        # Saving the same kind again replaces the old credential, so the
        # one-per-kind rule must not reject it as a duplicate.
        validators = []

    def validate(self, data):
        """Check the provider, model name, address and key fit together."""
        errors = {}
        errors["adapter"] = check_adapter(data)
        if errors["adapter"] == "":
            errors["model_name"] = check_model_name(data)
        errors["base_url"] = check_base_url(data)
        needs_key = data["adapter"] in KEY_REQUIRED_ADAPTERS
        if needs_key and not data.get("api_key"):
            errors["api_key"] = "This provider needs an API key."
        found = {}
        for field, message in errors.items():
            if message:
                found[field] = message
        if found:
            raise serializers.ValidationError(found)
        return data
