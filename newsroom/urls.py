"""Web addresses for news: /api/v1/news/..."""

from django.urls import path

from newsroom.views import NewsPreviewView

urlpatterns = [
    path("preview/", NewsPreviewView.as_view(), name="news-preview"),
]
