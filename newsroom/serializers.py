"""What an article looks like inside a post and in a topic preview."""

from rest_framework import serializers

from newsroom.models import Article


class ArticleSummarySerializer(serializers.ModelSerializer):
    """The article a post is based on: enough to credit and check it."""

    class Meta:
        model = Article
        fields = ["title", "url", "source_name", "published_at"]
        read_only_fields = fields


class ArticlePreviewSerializer(serializers.ModelSerializer):
    """An article in a topic preview, with where its text came from."""

    class Meta:
        model = Article
        fields = [
            "title",
            "url",
            "source_name",
            "source_tier",
            "published_at",
            "text_source",
        ]
        read_only_fields = fields


class TopicChoiceSerializer(serializers.Serializer):
    """One built-in topic a plan can follow."""

    key = serializers.CharField()
    label = serializers.CharField()
    category = serializers.CharField()
    description = serializers.CharField()


class TopicCatalogueSerializer(serializers.Serializer):
    """Every built-in topic, with the categories the picker groups them by."""

    categories = serializers.ListField(child=serializers.CharField())
    topics = TopicChoiceSerializer(many=True)
