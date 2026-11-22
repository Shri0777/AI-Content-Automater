"""API endpoints for the topic catalogue and previewing a topic's news."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from newsroom.presets import TOPIC_CATEGORIES, TOPIC_PRESETS
from newsroom.serializers import ArticlePreviewSerializer, TopicCatalogueSerializer
from newsroom.services import preview_topic


class NewsPreviewView(APIView):
    """The best articles stored for a topic preset right now."""

    @extend_schema(
        parameters=[
            OpenApiParameter("preset", OpenApiTypes.STR, required=True),
        ],
        responses=ArticlePreviewSerializer(many=True),
    )
    def get(self, request):
        """Return up to five articles a post on this topic could use."""
        articles = preview_topic(request.user, request.query_params.get("preset", ""))
        return Response(ArticlePreviewSerializer(articles, many=True).data)


class TopicCatalogueView(APIView):
    """Every built-in topic, for the topic picker."""

    @extend_schema(responses=TopicCatalogueSerializer)
    def get(self, request):
        """Return the categories and each topic's key, label and description."""
        topics = []
        for key, preset in TOPIC_PRESETS.items():
            topics.append({"key": key, **preset})
        catalogue = {"categories": TOPIC_CATEGORIES, "topics": topics}
        return Response(TopicCatalogueSerializer(catalogue).data)
