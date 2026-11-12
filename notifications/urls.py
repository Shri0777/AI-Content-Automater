"""Web addresses for notifications: /api/v1/notifications/..."""

from django.urls import path

from notifications.views import (
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
    UnreadCountView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("unread-count/", UnreadCountView.as_view(), name="unread-count"),
    path("read-all/", MarkAllReadView.as_view(), name="read-all"),
    path("<uuid:notification_id>/read/", MarkReadView.as_view(), name="mark-read"),
]
