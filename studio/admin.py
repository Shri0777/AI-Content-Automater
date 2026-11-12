"""Shows posts and their pipeline steps on the admin site."""

from django.contrib import admin

from studio.models import GenerationStep, Post, PostVersion


class PostVersionInline(admin.StackedInline):
    """Shows a post's versions on the post's admin page."""

    model = PostVersion
    extra = 0


class GenerationStepInline(admin.TabularInline):
    """Shows a post's pipeline steps on the post's admin page."""

    model = GenerationStep
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """How posts are listed in the admin site."""

    list_display = ["id", "plan", "status", "demo_mode", "created_at"]
    list_filter = ["status", "demo_mode"]
    inlines = [PostVersionInline, GenerationStepInline]
