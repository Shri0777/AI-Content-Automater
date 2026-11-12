"""Shows publications on the admin site for troubleshooting."""

from django.contrib import admin

from publishing.models import Publication


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    """How publications are listed in the admin site."""

    list_display = ["post", "account", "status", "external_id", "published_at"]
    list_filter = ["status"]
