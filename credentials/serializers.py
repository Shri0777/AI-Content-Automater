"""What credential data goes into and comes out of the API."""

from django.conf import settings
from rest_framework import serializers

from credentials.models import ADAPTERS_BY_KIND, KIND_CHOICES, ProviderCredential


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
            "updated_at",
        ]
        read_only_fields = ["id", "key_hint", "updated_at"]
        # Saving the same kind again replaces the old credential, so the
        # one-per-kind rule must not reject it as a duplicate.
        validators = []

    def validate(self, data):
        """Check the provider exists for this kind and is allowed right now."""
        allowed_adapters = ADAPTERS_BY_KIND[data["kind"]]
        if data["adapter"] not in allowed_adapters:
            raise serializers.ValidationError(
                {"adapter": f"Choose one of: {', '.join(allowed_adapters)}."}
            )
        if data["adapter"] == "demo" and not settings.DEMO_MODE:
            raise serializers.ValidationError(
                {"adapter": "Demo providers only work when DEMO_MODE is on."}
            )
        return data
