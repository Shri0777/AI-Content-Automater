"""Background jobs that keep schedules running.

make_slots_task (every hour) keeps every active plan's slots filled to its
schedule horizon. run_scheduler_task (every minute) starts posts that are
due, publishes approved posts whose time has come, and expires posts that
were not approved in time.
"""

from celery import shared_task

from planning.dispatcher import run_dispatcher
from planning.models import ContentPlan
from planning.schedule import make_slots
from publishing.scheduled import expire_late_approvals, publish_due_posts


@shared_task
def make_slots_task():
    """Create the coming slots of every active plan; return how many were new."""
    new_slots = 0
    plans = ContentPlan.objects.filter(paused=False).select_related("user")
    for plan in plans.prefetch_related("schedule_rules"):
        new_slots = new_slots + make_slots(plan)
    return new_slots


@shared_task
def run_scheduler_task():
    """Start due posts, publish the ones whose time has come, expire late ones."""
    counts = run_dispatcher()
    counts["published"] = publish_due_posts()
    counts["expired"] = expire_late_approvals()
    return counts
