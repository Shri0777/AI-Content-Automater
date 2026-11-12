"""Lets the operator view and change limits on Django's admin site."""

from django.contrib import admin

from quotas.models import QuotaOverride, QuotaPolicy, QuotaUsage


@admin.register(QuotaPolicy)
class QuotaPolicyAdmin(admin.ModelAdmin):
    """Tier limits. Change limit_value here to change a limit for everyone."""

    list_display = ["tier", "resource", "limit_value", "period", "applies_to"]
    list_filter = ["tier", "period"]
    list_editable = ["limit_value"]


@admin.register(QuotaOverride)
class QuotaOverrideAdmin(admin.ModelAdmin):
    """Special limits for individual users."""

    list_display = ["user", "resource", "limit_value", "note"]
    search_fields = ["user__email"]


@admin.register(QuotaUsage)
class QuotaUsageAdmin(admin.ModelAdmin):
    """Daily counters, shown read-only for troubleshooting."""

    list_display = ["user", "resource", "scope", "day", "used"]
    list_filter = ["resource", "day"]
    readonly_fields = ["user", "resource", "scope", "day", "used"]
