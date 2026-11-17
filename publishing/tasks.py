"""Background job that publishes an approved post.

Tasks only receive plain values (the post id as text), because Celery sends
them between processes as JSON.
"""

from celery import shared_task

from publishing.reconcile import reconcile_ambiguous
from publishing.services import publish_post
from studio.statuses import fail_after_crash


@shared_task
def publish_post_task(post_id):
    """Publish an approved post to its plan's social accounts."""
    try:
        return publish_post(post_id)
    except Exception:
        # Why this is here: see studio/tasks.py. A crash must not leave the
        # post stuck in "publishing" with no message for the user.
        fail_after_crash(post_id)
        raise


@shared_task
def reconcile_publications_task():
    """Try to settle publications whose outcome is unknown."""
    return reconcile_ambiguous()
