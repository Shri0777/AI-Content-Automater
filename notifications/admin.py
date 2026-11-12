"""Shows notifications on the admin site for troubleshooting."""

from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """How notifications are listed in the admin site."""

    list_display = ["user", "kind", "title", "created_at", "read_at"]
    list_filter = ["kind"]
    search_fields = ["user__email", "message"]
