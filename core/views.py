"""API endpoints that belong to no single feature, such as the health check."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers import HealthSerializer
from core.services import is_database_reachable


class HealthView(APIView):
    """Reports whether the API and its database are working."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(responses=HealthSerializer)
    def get(self, request):
        """Return "ok" when the database answers, otherwise a 503 error."""
        if is_database_reachable():
            return Response({"status": "ok", "database": "ok"})
        return Response({"status": "error", "database": "unreachable"}, status=503)
