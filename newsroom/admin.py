"""Shows stored news articles on the admin site."""

from django.contrib import admin

from newsroom.models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """How articles are listed in the admin site."""

    list_display = ["title", "source_name", "preset", "published_at"]
    list_filter = ["preset", "source_name"]
    search_fields = ["title"]
