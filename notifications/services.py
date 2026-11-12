"""Create, read and clean up in-app notifications.

Every feature tells users about events by calling notify(). There is no
email: users see notifications when they open the app (ADR-012).
"""

from datetime import timedelta

from django.utils import timezone

from core.errors import AppError
from notifications.models import KIND_CHOICES, Notification

KEEP_NOTIFICATIONS_FOR_DAYS = 60


class NotificationNotFound(AppError):
    """Raised when a notification does not exist or belongs to someone else."""

    status = 404
    code = "not_found"
    title = "Not found"


def title_for_kind(kind):
    """Return the title users see for a kind, or raise ValueError if unknown."""
    for known_kind, title in KIND_CHOICES:
        if known_kind == kind:
            return title
    raise ValueError(f"'{kind}' is not a known notification kind.")


def notify(user, kind, message, related=None, dedupe_key=""):
    """Create an in-app notification for user and return it.

    If dedupe_key is given and an unread notification with the same key
    already exists, that one is returned instead of creating a repeat.
    """
    title = title_for_kind(kind)
    if dedupe_key:
        existing = Notification.objects.filter(
            user=user, dedupe_key=dedupe_key, read_at=None
        ).first()
        if existing is not None:
            return existing
    notification = Notification(
        user=user, kind=kind, title=title, message=message, dedupe_key=dedupe_key
    )
    if related is not None:
        notification.related_type = type(related).__name__.lower()
        notification.related_id = related.id
    notification.save()
    return notification


def get_notifications(user, unread_only):
    """Return the user's notifications, optionally only the unread ones."""
    notifications = Notification.objects.filter(user=user)
    if unread_only:
        notifications = notifications.filter(read_at=None)
    return notifications


def count_unread(user):
    """Return how many notifications the user has not read yet."""
    return Notification.objects.filter(user=user, read_at=None).count()


def mark_read(user, notification_id):
    """Mark one of the user's notifications as read and return it."""
    notification = Notification.objects.filter(id=notification_id, user=user).first()
    if notification is None:
        raise NotificationNotFound("That notification does not exist.")
    notification.mark_as_read()
    return notification


def mark_all_read(user):
    """Mark every unread notification of the user as read; return how many."""
    unread = Notification.objects.filter(user=user, read_at=None)
    return unread.update(read_at=timezone.now())


def delete_old_notifications():
    """Delete notifications older than 60 days and return how many went."""
    cutoff = timezone.now() - timedelta(days=KEEP_NOTIFICATIONS_FOR_DAYS)
    deleted_count, deleted_by_table = Notification.objects.filter(
        created_at__lt=cutoff
    ).delete()
    return deleted_count
