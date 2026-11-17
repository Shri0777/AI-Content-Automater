"""Web addresses for publications: /api/v1/publications/..."""

from django.urls import path

from publishing.views import ResolvePublicationView

urlpatterns = [
    path(
        "<uuid:publication_id>/resolve/",
        ResolvePublicationView.as_view(),
        name="publication-resolve",
    ),
]
