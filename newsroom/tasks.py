"""Background job that reads the news for every topic in use."""

from celery import shared_task

from newsroom.ingest import ingest_active_presets


@shared_task
def ingest_news_task():
    """Read the sources of every preset an active plan follows."""
    return ingest_active_presets()
