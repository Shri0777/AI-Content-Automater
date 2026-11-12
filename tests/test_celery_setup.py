"""Tests that background jobs are wired up correctly.

V3 failed because its schedule named tasks that Celery never registered, and
one task returned database objects that could not be turned into JSON.
These tests guard against both mistakes.
"""

import json
import subprocess
import sys

from config.celery import app


def registered_task_names():
    """Return the names of all tasks Celery knows about, as a fresh worker would."""
    app.loader.import_default_modules()
    return list(app.tasks.keys())


def test_every_scheduled_job_points_to_a_registered_task():
    task_names = registered_task_names()

    for entry_name, entry in app.conf.beat_schedule.items():
        assert entry["task"] in task_names, f"{entry_name} names an unknown task"


def test_worker_health_task_is_registered():
    assert "core.tasks.check_worker_health" in registered_task_names()


def test_worker_health_task_result_can_be_sent_as_json():
    from core.tasks import check_worker_health

    result = check_worker_health.apply().get()

    assert json.loads(json.dumps(result)) == {"status": "ok"}


def test_tasks_are_registered_in_a_brand_new_python_process():
    script = (
        "import os; os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'\n"
        "import django; django.setup()\n"
        "from config.celery import app\n"
        "app.loader.import_default_modules()\n"
        "print('core.tasks.check_worker_health' in app.tasks)\n"
    )

    output = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )

    assert output.stdout.strip() == "True"
