"""API endpoints for the user's provider credentials."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from credentials import services
from credentials.models import ProviderCredential
from credentials.serializers import CredentialSerializer


class CredentialListView(APIView):
    """List the user's credentials, or save one."""

    @extend_schema(responses=CredentialSerializer(many=True))
    def get(self, request):
        """Return the user's credentials (never the keys themselves)."""
        credentials = ProviderCredential.objects.filter(user=request.user)
        return Response(CredentialSerializer(credentials, many=True).data)

    @extend_schema(request=CredentialSerializer, responses={201: CredentialSerializer})
    def post(self, request):
        """Save a credential; an existing one of the same kind is replaced."""
        serializer = CredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = services.save_credential(request.user, serializer.validated_data)
        return Response(CredentialSerializer(credential).data, status=201)


class CredentialDetailView(APIView):
    """Remove one credential."""

    @extend_schema(responses={204: None})
    def delete(self, request, credential_id):
        """Delete the credential if it belongs to the user."""
        services.delete_credential(request.user, credential_id)
        return Response(status=204)
