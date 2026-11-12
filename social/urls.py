"""Web addresses for social accounts: /api/v1/social/..."""

from django.urls import path

from social.views import (
    LinkDemoAccountView,
    SocialAccountDetailView,
    SocialAccountListView,
)

urlpatterns = [
    path("accounts/", SocialAccountListView.as_view(), name="social-accounts"),
    path(
        "accounts/<uuid:account_id>/",
        SocialAccountDetailView.as_view(),
        name="social-account-detail",
    ),
    path("link/demo/", LinkDemoAccountView.as_view(), name="social-link-demo"),
]
