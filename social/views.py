"""API endpoints for linking and unlinking social accounts."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from social import services
from social.serializers import SocialAccountSerializer


class SocialAccountListView(APIView):
    """List the user's linked accounts."""

    @extend_schema(responses=SocialAccountSerializer(many=True))
    def get(self, request):
        """Return every account the user has linked."""
        accounts = services.get_accounts(request.user)
        return Response(SocialAccountSerializer(accounts, many=True).data)


class SocialAccountDetailView(APIView):
    """Unlink one account."""

    @extend_schema(responses={204: None})
    def delete(self, request, account_id):
        """Remove the account if it belongs to the user."""
        services.unlink_account(request.user, account_id)
        return Response(status=204)


class LinkDemoAccountView(APIView):
    """Link an account on the fake demo network (demo mode only)."""

    @extend_schema(request=None, responses={201: SocialAccountSerializer})
    def post(self, request):
        """Create a demo account straight away; there is no login page."""
        account = services.link_demo_account(request.user)
        return Response(SocialAccountSerializer(account).data, status=201)
