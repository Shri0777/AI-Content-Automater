"""What post data comes out of the API."""

from django.urls import reverse
from rest_framework import serializers

from newsroom.serializers import ArticleSummarySerializer
from publishing.serializers import PublicationSerializer
from studio.models import GenerationStep, Post, PostVersion, Review


class ReviewSerializer(serializers.ModelSerializer):
    """The AI review of a version and its verdict."""

    class Meta:
        model = Review
        fields = ["scores", "issues", "verdict"]
        read_only_fields = fields


class PostVersionSerializer(serializers.ModelSerializer):
    """One version of a post's words and poster."""

    review = ReviewSerializer(read_only=True, default=None)

    class Meta:
        model = PostVersion
        fields = ["number", "headline", "caption", "image_prompt", "review"]
        read_only_fields = fields


class GenerationStepSerializer(serializers.ModelSerializer):
    """One stage run of the pipeline."""

    class Meta:
        model = GenerationStep
        fields = [
            "stage",
            "succeeded",
            "duration_ms",
            "error",
            "providers",
            "prompt_versions",
            "input_tokens",
            "output_tokens",
            "created_at",
        ]
        read_only_fields = fields


class PostSerializer(serializers.ModelSerializer):
    """A post in a list: its status and where it belongs."""

    plan_name = serializers.CharField(source="plan.name", read_only=True)
    topic_name = serializers.CharField(source="topic.name", default=None)
    # When a scheduled post is published; empty for "generate now" posts.
    scheduled_for = serializers.DateTimeField(
        source="slot.publish_at", default=None, read_only=True
    )

    class Meta:
        model = Post
        fields = [
            "id",
            "plan",
            "plan_name",
            "topic_name",
            "scheduled_for",
            "status",
            "status_reason",
            "demo_mode",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PostDetailSerializer(PostSerializer):
    """One post with everything made for it."""

    article = ArticleSummarySerializer(read_only=True)
    versions = PostVersionSerializer(many=True, read_only=True)
    steps = GenerationStepSerializer(many=True, read_only=True)
    publications = PublicationSerializer(many=True, read_only=True)
    poster_url = serializers.SerializerMethodField()

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + [
            "article",
            "poster_url",
            "versions",
            "steps",
            "publications",
        ]
        read_only_fields = fields

    def get_poster_url(self, post) -> str | None:
        """Return the address of the newest poster, or None if there is none."""
        version = post.latest_version()
        if version is None or not version.poster_path:
            return None
        return reverse("post-poster", args=[post.id])
