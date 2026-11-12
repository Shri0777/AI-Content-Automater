"""Background jobs that belong to no single feature.

Tasks must only receive and return plain values (text, numbers, lists and
dicts), because Celery sends them between processes as JSON.
"""

from celery import shared_task


@shared_task
def check_worker_health():
    """Return a tiny answer so we can prove a worker is running."""
    return {"status": "ok"}
