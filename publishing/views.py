"""API endpoint for settling a publication whose outcome is unknown."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from publishing.reconcile import resolve_publication
from publishing.serializers import PublicationSerializer, ResolveSerializer


class ResolvePublicationView(APIView):
    """Tell us whether a post we could not confirm really went out."""

    @extend_schema(request=ResolveSerializer, responses=PublicationSerializer)
    def post(self, request, publication_id):
        """Record the owner's answer and update the post."""
        serializer = ResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        publication = resolve_publication(
            request.user,
            publication_id,
            serializer.validated_data["outcome"],
            serializer.validated_data["external_id"],
        )
        return Response(PublicationSerializer(publication).data)
