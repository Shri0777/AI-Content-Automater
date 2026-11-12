"""Shows users on Django's admin site so the operator can look them up."""

from django.contrib import admin

from accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """How users are listed in the admin site. Passwords are never shown."""

    list_display = ["email", "tier", "is_staff", "date_joined"]
    search_fields = ["email"]
    ordering = ["email"]
    exclude = ["password"]
    readonly_fields = ["last_login", "date_joined"]
