"""Web addresses for the quotas app."""

from django.urls import path

from quotas.views import UsageView

urlpatterns = [
    path("me/usage/", UsageView.as_view(), name="usage"),
]
