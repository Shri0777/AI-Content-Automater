"""What content plan data goes into and comes out of the API."""

from zoneinfo import available_timezones

from rest_framework import serializers

from newsroom.presets import TOPIC_PRESETS
from planning.custom_topics import search_words_of
from planning.models import (
    APPROVAL_MODE_CHOICES,
    DEFAULT_AI_LABEL,
    DEFAULT_AUTO_POST_MIN_SCORE,
    DEFAULT_BRAND_COLOUR,
    ON_MISSED_APPROVAL_CHOICES,
    ContentPlan,
    PostSlot,
    ScheduleRule,
    Topic,
)
from social.serializers import SocialAccountSerializer


class TopicSerializer(serializers.ModelSerializer):
    """One topic of a plan: a built-in preset, or "custom" with search words."""

    preset = serializers.CharField(max_length=40)
    search_words = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default=""
    )
    instructions = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default=""
    )

    class Meta:
        model = Topic
        fields = ["id", "name", "preset", "search_words", "instructions"]
        read_only_fields = ["id"]

    def validate_preset(self, preset):
        """Accept a built-in preset, or "custom" for a new topic of the user's."""
        if preset == "custom" or preset in TOPIC_PRESETS:
            return preset
        raise serializers.ValidationError(f"'{preset}' is not a topic.")

    def validate(self, data):
        """A custom topic needs at least one word to look for in the news."""
        if data["preset"] == "custom" and not search_words_of(data["search_words"]):
            raise serializers.ValidationError(
                {"search_words": "Give at least one word to look for in the news."}
            )
        return data


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
            "ai_artwork_enabled",
            "brand_colour",
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
    # AI artwork on the cover slide; off unless asked for (it needs an image key).
    ai_artwork_enabled = serializers.BooleanField(default=False)
    # The slides' background colour, as "#RRGGBB".
    brand_colour = serializers.RegexField(
        r"^#[0-9A-Fa-f]{6}$", default=DEFAULT_BRAND_COLOUR
    )
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
    # Only for "auto" plans: the lowest total review score (out of 30) a
    # post needs to go out without your approval.
    auto_post_min_score = serializers.IntegerField(
        min_value=18, max_value=30, default=DEFAULT_AUTO_POST_MIN_SCORE
    )
    topics = TopicSerializer(many=True, allow_empty=False)
    account_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )
    schedule_rules = ScheduleRuleSerializer(many=True, required=False, default=list)
