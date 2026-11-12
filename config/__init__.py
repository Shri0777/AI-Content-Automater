"""Project configuration package.

Loading the Celery app here means it is ready whenever Django starts.
"""

from config.celery import app as celery_app

__all__ = ["celery_app"]
