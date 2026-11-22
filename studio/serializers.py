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
    slide_count = serializers.SerializerMethodField()

    class Meta:
        model = PostVersion
        fields = [
            "number",
            "headline",
            "caption",
            "image_prompt",
            "points",
            "figure",
            "quote",
            "takeaway",
            "slide_count",
            "edited_by_user",
            "review",
        ]
        read_only_fields = fields

    def get_slide_count(self, version) -> int:
        """Return how many slide images the version has (0 before slides)."""
        return len(version.slide_paths)


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
    # The final version's slides, in order (cover first).
    slide_urls = serializers.SerializerMethodField()
    # Which version is shown and published (Post.final_version).
    final_version = serializers.SerializerMethodField()

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + [
            "article",
            "poster_url",
            "slide_urls",
            "final_version",
            "versions",
            "steps",
            "publications",
        ]
        read_only_fields = fields

    def get_final_version(self, post) -> int | None:
        """Return the number of the version that is shown and published."""
        version = post.final_version()
        if version is None:
            return None
        return version.number

    def get_poster_url(self, post) -> str | None:
        """Return the address of the final poster, or None if there is none."""
        version = post.final_version()
        if version is None or not version.poster_path:
            return None
        return reverse("post-poster", args=[post.id])

    def get_slide_urls(self, post) -> list[str]:
        """Return the addresses of the final version's slides, cover first."""
        version = post.final_version()
        if version is None or version.image_expired:
            return []
        urls = []
        for number in range(1, len(version.slide_paths) + 1):
            urls.append(reverse("post-slide", args=[post.id, number]))
        return urls


class PostEditSerializer(serializers.Serializer):
    """The user's own wording for a post waiting for approval."""

    # Leave the headline out to keep the current one.
    headline = serializers.CharField(max_length=90, required=False, default="")
    # Leave the points out to keep the current ones.
    points = serializers.ListField(
        child=serializers.CharField(max_length=200), max_length=5, required=False
    )
    caption = serializers.CharField(max_length=3000)
