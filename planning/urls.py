"""Web addresses for content plans: /api/v1/plans/..."""

from django.urls import path

from planning.views import PlanDetailView, PlanListView

urlpatterns = [
    path("", PlanListView.as_view(), name="plans"),
    path("<uuid:plan_id>/", PlanDetailView.as_view(), name="plan-detail"),
]
