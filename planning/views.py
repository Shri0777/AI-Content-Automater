"""API endpoints for content plans."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from planning import services
from planning.serializers import (
    PlanCreateSerializer,
    PlanSerializer,
    PostSlotSerializer,
    ScheduleSerializer,
)


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


class PlanScheduleView(APIView):
    """Replace a plan's schedule."""

    @extend_schema(request=ScheduleSerializer, responses=PlanSerializer)
    def put(self, request, plan_id):
        """Save new rules and remake the slots that have not started yet."""
        serializer = ScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = services.replace_schedule(
            request.user, plan_id, serializer.validated_data["schedule_rules"]
        )
        return Response(PlanSerializer(plan).data)


class PausePlanView(APIView):
    """Stop a plan from posting."""

    @extend_schema(request=None, responses=PlanSerializer)
    def post(self, request, plan_id):
        """Pause the plan and remove its waiting slots."""
        plan = services.pause_plan(request.user, plan_id)
        return Response(PlanSerializer(plan).data)


class ResumePlanView(APIView):
    """Start a paused plan posting again."""

    @extend_schema(request=None, responses=PlanSerializer)
    def post(self, request, plan_id):
        """Resume the plan and make its coming slots."""
        plan = services.resume_plan(request.user, plan_id)
        return Response(PlanSerializer(plan).data)


class UpcomingSlotsView(APIView):
    """The plan's coming posting times."""

    @extend_schema(responses=PostSlotSerializer(many=True))
    def get(self, request, plan_id):
        """Return the slots from now on, soonest first."""
        slots = services.get_upcoming_slots(request.user, plan_id)
        return Response(PostSlotSerializer(slots, many=True).data)
