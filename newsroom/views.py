"""API endpoint for previewing the news a topic would use."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from newsroom.serializers import ArticlePreviewSerializer
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
