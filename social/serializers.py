"""What social account data goes in and out of the API. Tokens never go out."""

from rest_framework import serializers

from social.models import SocialAccount


class SocialAccountSerializer(serializers.ModelSerializer):
    """A linked social account, without its tokens."""

    # When the link stops working unless it is refreshed or linked again.
    link_expires_at = serializers.DateTimeField(
        source="token_expires_at", read_only=True
    )

    class Meta:
        model = SocialAccount
        fields = [
            "id",
            "platform",
            "network",
            "display_name",
            "status",
            "last_error",
            "link_expires_at",
            "created_at",
        ]
        read_only_fields = fields


class PlatformSerializer(serializers.Serializer):
    """One platform and whether accounts can be linked on it right now."""

    platform = serializers.CharField()
    name = serializers.CharField()
    link_method = serializers.ChoiceField(choices=["oauth", "api_key", "demo"])
    ready = serializers.BooleanField()


class BufferLinkSerializer(serializers.Serializer):
    """The Buffer API key, and optionally which channels to link."""

    api_key = serializers.CharField(write_only=True, max_length=500)
    channel_ids = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, max_length=50
    )


class LinkStartSerializer(serializers.Serializer):
    """Where to send the user to approve the link."""

    authorization_url = serializers.URLField()
