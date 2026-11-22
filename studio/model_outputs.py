"""The shape a text model's JSON answer must have, checked with serializers.

A model can answer with anything, so its answer is checked exactly like
data sent to our API: with a Django REST framework serializer. An answer
that does not fit is sent back to the model once to be fixed.
"""

from rest_framework import serializers


class BarOutput(serializers.Serializer):
    """One bar of a before-and-after comparison on the figure slide."""

    label = serializers.CharField(max_length=60)
    # The bar's length; display is what is written on it, such as "$2.50".
    amount = serializers.FloatField(min_value=0)
    display = serializers.CharField(max_length=40)


class FigureOutput(serializers.Serializer):
    """The one number that matters most, shown big on its own slide."""

    value = serializers.CharField(max_length=40)
    label = serializers.CharField(max_length=200)
    compare = BarOutput(many=True, required=False, allow_null=True, default=None)


class QuoteOutput(serializers.Serializer):
    """A sentence copied word for word from the article, with who said it."""

    text = serializers.CharField(max_length=400)
    speaker = serializers.CharField(max_length=120, allow_blank=True)


class DraftOutput(serializers.Serializer):
    """The answer to DRAFT_PROMPT and CORRECT_PROMPT.

    figure, quote and takeaway may be missing or null: an article without a
    real number or a strong quote gets no figure or quote slide.
    """

    headline = serializers.CharField(max_length=200)
    # One slide per point. A thin article may support only one or two.
    points = serializers.ListField(
        child=serializers.CharField(max_length=300), min_length=1, max_length=8
    )
    figure = FigureOutput(required=False, allow_null=True, default=None)
    quote = QuoteOutput(required=False, allow_null=True, default=None)
    takeaway = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default=""
    )
    caption = serializers.CharField(max_length=4000)


class ImagePromptOutput(serializers.Serializer):
    """The answer to IMAGE_PROMPT_PROMPT."""

    prompt = serializers.CharField(max_length=1000)


class ScoresOutput(serializers.Serializer):
    """The six review scores, each a whole number from 1 to 5."""

    grounding = serializers.IntegerField(min_value=1, max_value=5)
    relevance = serializers.IntegerField(min_value=1, max_value=5)
    clarity = serializers.IntegerField(min_value=1, max_value=5)
    tone = serializers.IntegerField(min_value=1, max_value=5)
    safety = serializers.IntegerField(min_value=1, max_value=5)
    shareability = serializers.IntegerField(min_value=1, max_value=5)


class IssueOutput(serializers.Serializer):
    """One problem the reviewer found."""

    severity = serializers.ChoiceField(choices=["minor", "blocker"])
    problem = serializers.CharField(max_length=500)
    fix_instruction = serializers.CharField(max_length=500, allow_blank=True)


class ArticleScoreOutput(serializers.Serializer):
    """The scores of one shortlisted article."""

    number = serializers.IntegerField(min_value=1)
    relevance = serializers.IntegerField(min_value=1, max_value=5)
    credibility = serializers.IntegerField(min_value=1, max_value=5)
    novelty = serializers.IntegerField(min_value=1, max_value=5)
    verifiable = serializers.BooleanField()


class ArticleScoresOutput(serializers.Serializer):
    """The answer to ARTICLE_SCORES_PROMPT."""

    scores = ArticleScoreOutput(many=True)


class ReviewOutput(serializers.Serializer):
    """The answer to REVIEW_PROMPT."""

    scores = ScoresOutput()
    issues = IssueOutput(many=True)
