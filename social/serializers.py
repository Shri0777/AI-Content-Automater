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
    # For X, LinkedIn and Facebook: did the user save their own developer
    # app, and the address to register in it as the callback/redirect URL.
    app_saved = serializers.BooleanField()
    callback_url = serializers.CharField(allow_null=True)


class PlatformAppSerializer(serializers.Serializer):
    """A saved developer app. The secret is never sent back."""

    platform = serializers.CharField()
    client_id = serializers.CharField()
    updated_at = serializers.DateTimeField()


class PlatformAppInputSerializer(serializers.Serializer):
    """A developer app's id and secret, copied from the platform's site."""

    client_id = serializers.CharField(max_length=255)
    client_secret = serializers.CharField(max_length=500)


class BufferLinkSerializer(serializers.Serializer):
    """The Buffer API key, and optionally which channels to link."""

    api_key = serializers.CharField(write_only=True, max_length=500)
    channel_ids = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, max_length=50
    )


class BufferKeySerializer(serializers.Serializer):
    """A Buffer API key, to look up the user's channels."""

    api_key = serializers.CharField(write_only=True, max_length=500)


class BufferChannelSerializer(serializers.Serializer):
    """One Buffer channel the user can choose to link."""

    id = serializers.CharField()
    name = serializers.CharField()
    network = serializers.CharField()


class LinkStartSerializer(serializers.Serializer):
    """Where to send the user to approve the link."""

    authorization_url = serializers.URLField()
