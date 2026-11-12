"""Shows linked social accounts on the admin site. Tokens are hidden."""

from django.contrib import admin

from social.models import SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """How social accounts are listed in the admin site."""

    list_display = ["display_name", "user", "platform", "status", "created_at"]
    list_filter = ["platform", "status"]
    exclude = ["encrypted_token"]
