"""Web addresses for social accounts: /api/v1/social/..."""

from django.urls import path

from social.views import (
    BufferChannelsView,
    LinkBufferView,
    LinkCallbackView,
    LinkDemoAccountView,
    LinkStartView,
    PlatformAppDetailView,
    PlatformAppListView,
    PlatformListView,
    SocialAccountDetailView,
    SocialAccountListView,
)

urlpatterns = [
    path("platforms/", PlatformListView.as_view(), name="social-platforms"),
    path("apps/", PlatformAppListView.as_view(), name="social-apps"),
    path(
        "apps/<str:platform>/",
        PlatformAppDetailView.as_view(),
        name="social-app-detail",
    ),
    path("accounts/", SocialAccountListView.as_view(), name="social-accounts"),
    path(
        "accounts/<uuid:account_id>/",
        SocialAccountDetailView.as_view(),
        name="social-account-detail",
    ),
    path("link/demo/", LinkDemoAccountView.as_view(), name="social-link-demo"),
    path("link/buffer/", LinkBufferView.as_view(), name="social-link-buffer"),
    path(
        "buffer/channels/",
        BufferChannelsView.as_view(),
        name="social-buffer-channels",
    ),
    path(
        "link/<str:platform>/start/",
        LinkStartView.as_view(),
        name="social-link-start",
    ),
    path(
        "link/<str:platform>/callback/",
        LinkCallbackView.as_view(),
        name="social-link-callback",
    ),
]
