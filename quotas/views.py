"""API endpoint that shows a user their limits and usage."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from quotas.serializers import UsageSerializer
from quotas.services import get_usage_summary


class UsageView(APIView):
    """Every free-tier limit, how much is used, and when daily ones reset."""

    @extend_schema(responses=UsageSerializer)
    def get(self, request):
        """Return the logged-in user's limits and usage."""
        return Response(get_usage_summary(request.user))
