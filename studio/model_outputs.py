"""The shape a text model's JSON answer must have, checked with serializers.

A model can answer with anything, so its answer is checked exactly like
data sent to our API: with a Django REST framework serializer. An answer
that does not fit is sent back to the model once to be fixed.
"""

from rest_framework import serializers


class DraftOutput(serializers.Serializer):
    """The answer to DRAFT_PROMPT."""

    headline = serializers.CharField(max_length=200)
    caption = serializers.CharField(max_length=3000)


class ImagePromptOutput(serializers.Serializer):
    """The answer to IMAGE_PROMPT_PROMPT."""

    prompt = serializers.CharField(max_length=1000)


class ScoresOutput(serializers.Serializer):
    """The five review scores, each a whole number from 1 to 5."""

    grounding = serializers.IntegerField(min_value=1, max_value=5)
    relevance = serializers.IntegerField(min_value=1, max_value=5)
    clarity = serializers.IntegerField(min_value=1, max_value=5)
    tone = serializers.IntegerField(min_value=1, max_value=5)
    safety = serializers.IntegerField(min_value=1, max_value=5)


class IssueOutput(serializers.Serializer):
    """One problem the reviewer found."""

    severity = serializers.ChoiceField(choices=["minor", "blocker"])
    problem = serializers.CharField(max_length=500)
    fix_instruction = serializers.CharField(max_length=500, allow_blank=True)


class ReviewOutput(serializers.Serializer):
    """The answer to REVIEW_PROMPT."""

    scores = ScoresOutput()
    issues = IssueOutput(many=True)
