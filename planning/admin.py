"""Shows content plans and their topics on the admin site."""

from django.contrib import admin

from planning.models import ContentPlan, Topic


class TopicInline(admin.TabularInline):
    """Shows a plan's topics on the plan's admin page."""

    model = Topic
    extra = 0


@admin.register(ContentPlan)
class ContentPlanAdmin(admin.ModelAdmin):
    """How plans are listed in the admin site."""

    list_display = ["name", "user", "approval_mode", "paused", "created_at"]
    list_filter = ["approval_mode", "paused"]
    inlines = [TopicInline]
