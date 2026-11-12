"""What an article looks like when shown inside a post."""

from rest_framework import serializers

from newsroom.models import Article


class ArticleSummarySerializer(serializers.ModelSerializer):
    """The article a post is based on: enough to credit and check it."""

    class Meta:
        model = Article
        fields = ["title", "url", "source_name", "published_at"]
        read_only_fields = fields
