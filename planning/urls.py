"""Web addresses for content plans: /api/v1/plans/..."""

from django.urls import path

from planning.views import (
    PausePlanView,
    PlanDetailView,
    PlanListView,
    PlanScheduleView,
    ResumePlanView,
    UpcomingSlotsView,
)

urlpatterns = [
    path("", PlanListView.as_view(), name="plans"),
    path("<uuid:plan_id>/", PlanDetailView.as_view(), name="plan-detail"),
    path("<uuid:plan_id>/schedule/", PlanScheduleView.as_view(), name="plan-schedule"),
    path("<uuid:plan_id>/pause/", PausePlanView.as_view(), name="plan-pause"),
    path("<uuid:plan_id>/resume/", ResumePlanView.as_view(), name="plan-resume"),
    path("<uuid:plan_id>/upcoming/", UpcomingSlotsView.as_view(), name="plan-upcoming"),
]
