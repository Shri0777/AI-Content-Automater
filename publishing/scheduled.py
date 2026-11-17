"""Publish scheduled posts at their time, and expire ones approved too late.

Runs every minute with the dispatcher (planning/tasks.py). Publishing a post
twice is harmless: publish_post() moves it from "approved" only once, and
each account gets one Publication (its idempotency key is unique).
"""

from datetime import timedelta

from django.utils import timezone

from notifications.services import notify
from publishing.tasks import publish_post_task
from studio.models import Post
from studio.statuses import StatusChangeNotAllowed, change_status


def publish_due_posts(now=None):
    """Queue publishing for approved posts whose time has come; return how many."""
    if now is None:
        now = timezone.now()
    due_posts = Post.objects.filter(status="approved", slot__publish_at__lte=now)
    count = 0
    for post in due_posts:
        publish_post_task.delay(str(post.id))
        count = count + 1
    return count


def approval_deadline(post):
    """Return the last moment the post can still be approved and published."""
    allowed_delay = timedelta(minutes=post.plan.max_lateness_minutes)
    return post.slot.publish_at + allowed_delay


def expire_late_approvals(now=None):
    """Expire waiting posts whose plan drops late ones; return how many."""
    if now is None:
        now = timezone.now()
    waiting = Post.objects.filter(
        status="awaiting_approval",
        slot__publish_at__lt=now,
        plan__on_missed_approval="expire",
    ).select_related("plan", "slot", "user")
    count = 0
    for post in waiting:
        if approval_deadline(post) >= now:
            continue
        try:
            change_status(post, "expired", "Nobody approved it before its time.")
        except StatusChangeNotAllowed:
            # Approved or rejected at this very moment: leave it.
            continue
        notify(
            post.user,
            "post_expired",
            "A post expired before it was approved.",
            related=post,
        )
        count = count + 1
    return count
