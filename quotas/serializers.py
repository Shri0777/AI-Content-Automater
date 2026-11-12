"""What the usage endpoint sends back."""

from rest_framework import serializers


class LimitUsageSerializer(serializers.Serializer):
    """One limit and how much of it is used."""

    resource = serializers.CharField()
    description = serializers.CharField()
    period = serializers.CharField()
    applies_to = serializers.CharField()
    limit = serializers.IntegerField()
    used = serializers.IntegerField(allow_null=True)
    resets_at = serializers.DateTimeField(allow_null=True)


class UsageSerializer(serializers.Serializer):
    """All of a user's limits."""

    tier = serializers.CharField()
    limits = LimitUsageSerializer(many=True)
