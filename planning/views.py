"""API endpoints for content plans."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from planning import services
from planning.serializers import PlanCreateSerializer, PlanSerializer


class PlanListView(APIView):
    """List the user's plans, or create one."""

    @extend_schema(responses=PlanSerializer(many=True))
    def get(self, request):
        """Return the user's plans."""
        plans = services.get_plans(request.user)
        return Response(PlanSerializer(plans, many=True).data)

    @extend_schema(request=PlanCreateSerializer, responses={201: PlanSerializer})
    def post(self, request):
        """Create a plan with its topics and target accounts."""
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = services.create_plan(request.user, serializer.validated_data)
        return Response(PlanSerializer(plan).data, status=201)


class PlanDetailView(APIView):
    """Show or delete one plan."""

    @extend_schema(responses=PlanSerializer)
    def get(self, request, plan_id):
        """Return one of the user's plans."""
        plan = services.get_plan(request.user, plan_id)
        return Response(PlanSerializer(plan).data)

    @extend_schema(responses={204: None})
    def delete(self, request, plan_id):
        """Delete the plan and every post made for it."""
        services.delete_plan(request.user, plan_id)
        return Response(status=204)
