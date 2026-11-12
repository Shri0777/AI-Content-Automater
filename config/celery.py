"""Create the Celery app that runs background jobs.

Celery reads every setting that starts with CELERY_ from Django's settings,
and finds the jobs (tasks) in each app's tasks.py file.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("ai_content_automator")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
