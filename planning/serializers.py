"""What content plan data goes into and comes out of the API."""

from rest_framework import serializers

from newsroom.presets import PRESET_CHOICES
from planning.models import (
    APPROVAL_MODE_CHOICES,
    DEFAULT_AI_LABEL,
    ContentPlan,
    Topic,
)
from social.serializers import SocialAccountSerializer


class TopicSerializer(serializers.ModelSerializer):
    """One topic of a plan."""

    preset = serializers.ChoiceField(choices=PRESET_CHOICES)

    class Meta:
        model = Topic
        fields = ["id", "name", "preset"]
        read_only_fields = ["id"]


class PlanSerializer(serializers.ModelSerializer):
    """A plan as the API shows it, with its topics and accounts."""

    topics = TopicSerializer(many=True, read_only=True)
    accounts = SocialAccountSerializer(many=True, read_only=True)

    class Meta:
        model = ContentPlan
        fields = [
            "id",
            "name",
            "requirements",
            "approval_mode",
            "ai_label_enabled",
            "ai_label_text",
            "paused",
            "topics",
            "accounts",
            "created_at",
        ]
        read_only_fields = fields


class PlanCreateSerializer(serializers.Serializer):
    """The details needed to create a plan."""

    name = serializers.CharField(max_length=100)
    requirements = serializers.CharField(required=False, default="", allow_blank=True)
    approval_mode = serializers.ChoiceField(
        choices=APPROVAL_MODE_CHOICES, default="manual"
    )
    ai_label_enabled = serializers.BooleanField(default=True)
    ai_label_text = serializers.CharField(max_length=100, default=DEFAULT_AI_LABEL)
    topics = TopicSerializer(many=True, allow_empty=False)
    account_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )
