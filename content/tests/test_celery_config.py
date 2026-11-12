"""Consistency tests for the Celery configuration.

CELERY_BEAT_SCHEDULE must reference task names that Celery actually
registers. ``@shared_task`` registers a task under the *full dotted path of
the module that defines it*, so a schedule entry using a shortened path
would make Celery Beat fail to find the task on every tick and the job
would never run.
"""

from django.conf import settings
from django.test import TestCase

# Importing the task modules registers their tasks in the Celery registry.
# These are the same modules the worker imports through autodiscovery.
import content.tasks.campaign_tasks as campaign_tasks  # noqa: F401
import content.tasks.publishing_tasks as publishing_tasks  # noqa: F401
from content_automater.celery import app


class CeleryBeatScheduleTest(TestCase):
    """Every scheduled task name must match a registered Celery task."""

    def test_schedule_references_registered_task_names(self):
        for entry_key, entry in settings.CELERY_BEAT_SCHEDULE.items():
            task_name = entry["task"]
            self.assertIn(
                task_name,
                app.tasks,
                f"Beat schedule {entry_key!r} references unregistered task "
                f"{task_name!r} — the scheduled job would never run.",
            )
