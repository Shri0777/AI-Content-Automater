"""Web addresses for credentials: /api/v1/credentials/..."""

from django.urls import path

from credentials.views import CredentialDetailView, CredentialListView

urlpatterns = [
    path("", CredentialListView.as_view(), name="credentials"),
    path(
        "<uuid:credential_id>/",
        CredentialDetailView.as_view(),
        name="credential-detail",
    ),
]
