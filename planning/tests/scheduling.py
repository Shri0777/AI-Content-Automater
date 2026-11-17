"""Small helpers for the scheduling tests."""

from datetime import UTC, datetime

from planning.models import ScheduleRule


def utc(text):
    """Return a UTC datetime from "YYYY-MM-DD HH:MM"."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def add_rule(plan, days, times, zone):
    """Give plan a schedule rule and return it."""
    return ScheduleRule.objects.create(
        plan=plan, days_of_week=days, times=times, timezone=zone
    )
