"""Background job that moves a post through the pipeline stages.

Tasks only receive plain values (the post id as text), because Celery sends
them between processes as JSON.
"""

from celery import shared_task

from studio.pipeline import STAGES, run_stage
from studio.statuses import fail_after_crash


@shared_task
def advance_post_task(post_id):
    """Run the post's current stage, then queue the next one if there is one."""
    try:
        new_status = run_stage(post_id)
    except Exception:
        # Why this is here: without it, a bug would leave the post stuck in a
        # working status forever, with no message for the user (this happened
        # in V3). The error is raised again so the worker logs it in full.
        fail_after_crash(post_id)
        raise
    if new_status in STAGES:
        advance_post_task.delay(post_id)
    return new_status
