"""Check that the installed app can really start: database, broker and tasks.

The unit tests run with development tools installed. This script is meant to
run with only the production packages (inside the Docker image), so it
catches a package that production needs but nobody listed. That exact
mistake once stopped the background worker from starting while every unit
test still passed.

Run it inside the image:
    docker compose run --rm worker python scripts/smoke_check.py
"""

import os
import sys
from pathlib import Path

import django

# "python scripts/smoke_check.py" puts the scripts folder on Python's import
# path, not the project folder. Add the project folder so "config" is found.
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_FOLDER))


def broker_is_reachable(celery_app):
    """Return True if Celery can connect to its message broker (Redis)."""
    try:
        with celery_app.connection() as connection:
            connection.ensure_connection(max_retries=3)
    except Exception as error:
        # Any failure counts here, including a missing package, so report it.
        print(f"Broker check failed: {type(error).__name__}: {error}")
        return False
    return True


def find_unregistered_scheduled_tasks(celery_app):
    """Return scheduled task names that Celery does not know about."""
    celery_app.loader.import_default_modules()
    missing = []
    for entry in celery_app.conf.beat_schedule.values():
        if entry["task"] not in celery_app.tasks:
            missing.append(entry["task"])
    return missing


def main():
    """Run every check and exit with code 1 if any of them fails."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()
    # These imports need Django to be set up first, so they live here.
    from config.celery import app
    from core.services import is_database_reachable

    problems = []
    if not is_database_reachable():
        problems.append("The database is not reachable.")
    if not broker_is_reachable(app):
        problems.append("The message broker (Redis) is not reachable.")
    for task_name in find_unregistered_scheduled_tasks(app):
        problems.append(f"Scheduled task '{task_name}' is not registered.")

    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        sys.exit(1)
    print("Smoke check passed: database, broker and scheduled tasks are ready.")


if __name__ == "__main__":
    main()
