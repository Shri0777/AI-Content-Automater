"""
Celery application configuration for background task processing.

Implements FR-029 (campaign execution), FR-030 (scheduled publishing),
and FR-038 (notifications) via asynchronous task workers.
"""
import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'content_automater.settings.development')

app = Celery('content_automater')

# Load configuration from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for verification."""
    print(f'Request: {self.request!r}')
