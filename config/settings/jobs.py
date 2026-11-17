"""The timetable of background jobs (imported by base.py).

Celery Beat starts each "task" on its "schedule". Every task named here
must be a real, registered task; tests/test_celery_setup.py checks this.
"""

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "delete-old-notifications": {
        "task": "notifications.tasks.delete_old_notifications_task",
        "schedule": crontab(hour=3, minute=0),
    },
    # Deletes old posters, article text and records (core/maintenance.py).
    "nightly-cleanup": {
        "task": "core.tasks.nightly_cleanup_task",
        "schedule": crontab(hour=3, minute=30),
    },
    # Reads the news for every topic in use (shared by all users).
    "ingest-news": {
        "task": "newsroom.tasks.ingest_news_task",
        "schedule": crontab(minute="10,40"),
    },
    # Settles posts that were sent but never confirmed by the platform.
    "reconcile-publications": {
        "task": "publishing.tasks.reconcile_publications_task",
        "schedule": crontab(minute="*/10"),
    },
    # Keeps every plan's slots filled up to its schedule horizon.
    "make-slots": {
        "task": "planning.tasks.make_slots_task",
        "schedule": crontab(minute=5),
    },
    # Starts due posts, publishes approved ones on time, expires late ones.
    "run-scheduler": {
        "task": "planning.tasks.run_scheduler_task",
        "schedule": crontab(),
    },
    # X tokens last two hours, so this runs often enough to keep them fresh.
    "refresh-social-tokens": {
        "task": "social.tasks.refresh_social_tokens_task",
        "schedule": crontab(minute="*/30"),
    },
}
