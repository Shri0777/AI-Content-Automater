"""API endpoints for reading notifications. The frontend polls these."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications import services
from notifications.serializers import (
    MarkedReadSerializer,
    NotificationSerializer,
    UnreadCountSerializer,
)


class NotificationPagination(CursorPagination):
    """Show notifications 20 at a time, newest first."""

    page_size = 20
    ordering = "-created_at"


class NotificationListView(APIView):
    """The logged-in user's notifications."""

    @extend_schema(
        parameters=[OpenApiParameter("unread", OpenApiTypes.BOOL)],
        responses=NotificationSerializer(many=True),
    )
    def get(self, request):
        """Return one page of notifications; add ?unread=true for unread only."""
        unread_only = request.query_params.get("unread") == "true"
        notifications = services.get_notifications(request.user, unread_only)
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(notifications, request, view=self)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class UnreadCountView(APIView):
    """How many notifications are unread (cheap enough to poll often)."""

    @extend_schema(responses=UnreadCountSerializer)
    def get(self, request):
        """Return the number of unread notifications."""
        return Response({"unread": services.count_unread(request.user)})


class MarkReadView(APIView):
    """Mark one notification as read."""

    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, notification_id):
        """Mark the notification as read and return it."""
        notification = services.mark_read(request.user, notification_id)
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    """Mark all of the user's notifications as read."""

    @extend_schema(request=None, responses=MarkedReadSerializer)
    def post(self, request):
        """Mark everything read and say how many changed."""
        return Response({"marked_read": services.mark_all_read(request.user)})
