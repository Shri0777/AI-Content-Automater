"""Shapes of the data that core endpoints send back."""

from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    """The answer from the health check endpoint."""

    status = serializers.CharField()
    database = serializers.CharField()
