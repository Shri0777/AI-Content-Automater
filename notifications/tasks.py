"""Background jobs for notifications."""

from celery import shared_task

from notifications.services import delete_old_notifications


@shared_task
def delete_old_notifications_task():
    """Delete notifications older than 60 days (runs every night)."""
    return {"deleted": delete_old_notifications()}
