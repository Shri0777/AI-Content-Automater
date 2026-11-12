"""What a publication looks like in the API."""

from rest_framework import serializers

from publishing.models import Publication


class PublicationSerializer(serializers.ModelSerializer):
    """Where a post was sent and what happened."""

    account_name = serializers.CharField(
        source="account.display_name", default=None, read_only=True
    )
    platform = serializers.CharField(
        source="account.platform", default=None, read_only=True
    )

    class Meta:
        model = Publication
        fields = [
            "id",
            "account_name",
            "platform",
            "status",
            "external_id",
            "error",
            "demo_mode",
            "published_at",
        ]
        read_only_fields = fields
