"""What content plan data goes into and comes out of the API."""

from zoneinfo import available_timezones

from rest_framework import serializers

from newsroom.presets import PRESET_CHOICES
from planning.models import (
    APPROVAL_MODE_CHOICES,
    DEFAULT_AI_LABEL,
    DEFAULT_AUTO_POST_MIN_SCORE,
    ON_MISSED_APPROVAL_CHOICES,
    ContentPlan,
    PostSlot,
    ScheduleRule,
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


def check_clock_time(text):
    """Raise ValidationError unless text is a time like "09:30"."""
    parts = text.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise serializers.ValidationError(f"'{text}' is not a time like 09:30.")
    if len(parts[1]) != 2 or int(parts[0]) > 23 or int(parts[1]) > 59:
        raise serializers.ValidationError(f"'{text}' is not a time like 09:30.")


class ScheduleRuleSerializer(serializers.ModelSerializer):
    """Some weekdays (Monday = 0 ... Sunday = 6) at some local times."""

    days_of_week = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        allow_empty=False,
        max_length=7,
    )
    times = serializers.ListField(
        child=serializers.CharField(max_length=5), allow_empty=False, max_length=24
    )
    # Leave it out to use the account's own timezone.
    timezone = serializers.CharField(max_length=64, required=False, allow_blank=True)

    class Meta:
        model = ScheduleRule
        fields = ["id", "days_of_week", "times", "timezone"]
        read_only_fields = ["id"]

    def validate_times(self, times):
        """Check every time looks like "HH:MM"."""
        for text in times:
            check_clock_time(text)
        return times

    def validate_timezone(self, name):
        """Check the timezone is a real IANA name, such as "Asia/Kolkata"."""
        if name and name not in available_timezones():
            raise serializers.ValidationError(f"'{name}' is not a known timezone.")
        return name


class ScheduleSerializer(serializers.Serializer):
    """A plan's whole schedule, for replacing it in one go."""

    schedule_rules = ScheduleRuleSerializer(many=True)


class PostSlotSerializer(serializers.ModelSerializer):
    """One coming slot: when it posts, and its post once started."""

    post = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PostSlot
        fields = ["id", "publish_at", "generate_at", "status", "post"]
        read_only_fields = fields


class PlanSerializer(serializers.ModelSerializer):
    """A plan as the API shows it, with its topics, accounts and schedule."""

    topics = TopicSerializer(many=True, read_only=True)
    accounts = SocialAccountSerializer(many=True, read_only=True)
    schedule_rules = ScheduleRuleSerializer(many=True, read_only=True)

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
            "lead_time_minutes",
            "max_lateness_minutes",
            "on_missed_approval",
            "auto_post_min_score",
            "topics",
            "accounts",
            "schedule_rules",
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
    # Start making a post this long before its time (15 minutes to 1 day).
    lead_time_minutes = serializers.IntegerField(
        min_value=15, max_value=1440, default=60
    )
    # Skip a post that cannot start this long after its time (5 to 240).
    max_lateness_minutes = serializers.IntegerField(
        min_value=5, max_value=240, default=30
    )
    on_missed_approval = serializers.ChoiceField(
        choices=ON_MISSED_APPROVAL_CHOICES, default="expire"
    )
    # Only for "auto" plans: the lowest total review score (out of 25) a
    # post needs to go out without your approval.
    auto_post_min_score = serializers.IntegerField(
        min_value=15, max_value=25, default=DEFAULT_AUTO_POST_MIN_SCORE
    )
    topics = TopicSerializer(many=True, allow_empty=False)
    account_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )
    schedule_rules = ScheduleRuleSerializer(many=True, required=False, default=list)
