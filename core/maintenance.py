"""The nightly clean-up: retention rules from design/system-design.md §17.9.

| Data                       | Kept for                                  |
|----------------------------|-------------------------------------------|
| Poster and artwork images  | the user's poster_retention_days (30)     |
| Article text               | 14 days (title, link and source: longer)  |
| Unused articles            | 90 days                                   |
| Pipeline step records      | 90 days                                   |
| Unfinished link attempts   | 1 day                                     |
| Daily news request counts  | 30 days                                   |
| Notifications              | 60 days (notifications/services.py)       |
| Posts, versions, publications | kept as the user's history             |
"""

from datetime import timedelta

from django.utils import timezone

from core.disk import disk_is_nearly_full
from newsroom.retention import (
    clear_old_text,
    delete_old_budgets,
    delete_old_unused_articles,
)
from social.models import LinkAttempt
from studio.retention import delete_old_steps, expire_old_images

LINK_ATTEMPT_RETENTION = timedelta(days=1)


def delete_old_link_attempts(now):
    """Delete connect-an-account attempts older than a day."""
    deleted, _ = LinkAttempt.objects.filter(
        created_at__lt=now - LINK_ATTEMPT_RETENTION
    ).delete()
    return deleted


def run_cleanup(now=None):
    """Apply every retention rule; return how much each one removed."""
    if now is None:
        now = timezone.now()
    disk_is_nearly_full()
    return {
        "images_expired": expire_old_images(now),
        "article_texts_cleared": clear_old_text(now),
        "articles_deleted": delete_old_unused_articles(now),
        "steps_deleted": delete_old_steps(now),
        "link_attempts_deleted": delete_old_link_attempts(now),
        "budgets_deleted": delete_old_budgets(now),
    }
