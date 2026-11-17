"""Background jobs that belong to no single feature.

Tasks must only receive and return plain values (text, numbers, lists and
dicts), because Celery sends them between processes as JSON.
"""

from celery import shared_task

from core.maintenance import run_cleanup


@shared_task
def check_worker_health():
    """Return a tiny answer so we can prove a worker is running."""
    return {"status": "ok"}


@shared_task
def nightly_cleanup_task():
    """Apply the retention rules (core/maintenance.py)."""
    return run_cleanup()
