"""Shows linked social accounts on the admin site. Tokens are hidden."""

from django.contrib import admin

from social.models import PlatformApp, SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """How social accounts are listed in the admin site."""

    list_display = ["display_name", "user", "platform", "status", "created_at"]
    list_filter = ["platform", "status"]
    exclude = ["encrypted_token"]


@admin.register(PlatformApp)
class PlatformAppAdmin(admin.ModelAdmin):
    """How users' developer apps are listed. The secret is hidden."""

    list_display = ["platform", "user", "client_id", "updated_at"]
    list_filter = ["platform"]
    exclude = ["encrypted_client_secret"]
