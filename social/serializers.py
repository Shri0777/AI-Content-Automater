"""What social account data goes out of the API. Tokens are never included."""

from rest_framework import serializers

from social.models import SocialAccount


class SocialAccountSerializer(serializers.ModelSerializer):
    """A linked social account, without its token."""

    class Meta:
        model = SocialAccount
        fields = ["id", "platform", "display_name", "status", "created_at"]
        read_only_fields = fields
