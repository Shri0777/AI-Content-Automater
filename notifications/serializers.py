"""What notification data the API sends back."""

from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """One notification as the frontend sees it."""

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "title",
            "message",
            "related_type",
            "related_id",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    """How many notifications are unread."""

    unread = serializers.IntegerField()


class MarkedReadSerializer(serializers.Serializer):
    """How many notifications were just marked as read."""

    marked_read = serializers.IntegerField()
