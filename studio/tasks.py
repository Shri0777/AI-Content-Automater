"""Background job that moves a post through the pipeline stages.

Tasks only receive plain values (the post id as text, a number), because
Celery sends them between processes as JSON.
"""

from celery import shared_task

from studio.pipeline import STAGES
from studio.runner import TryAgainLater, run_stage
from studio.statuses import fail_after_crash

# A stage whose provider is busy is tried up to 3 more times: after 30
# seconds, then 60, then 120. After that the post fails.
MAX_RETRIES = 3
FIRST_RETRY_SECONDS = 30


def retry_delay_seconds(attempt):
    """Return how long to wait after a busy attempt: it doubles each time."""
    return FIRST_RETRY_SECONDS * 2 ** (attempt - 1)


@shared_task
def advance_post_task(post_id, attempt=1):
    """Run the post's current stage, then queue the next one if there is one.

    attempt counts the tries of the current stage, starting at 1.
    """
    try:
        new_status = run_stage(post_id, can_retry=attempt <= MAX_RETRIES)
    except TryAgainLater:
        # Why this is here: rate limits and timeouts usually pass, so the
        # same stage is queued again a little later instead of failing.
        advance_post_task.apply_async(
            [post_id, attempt + 1], countdown=retry_delay_seconds(attempt)
        )
        return "retrying"
    except Exception:
        # Why this is here: without it, a bug would leave the post stuck in a
        # working status forever, with no message for the user (this happened
        # in V3). The error is raised again so the worker logs it in full.
        fail_after_crash(post_id)
        raise
    if new_status in STAGES:
        advance_post_task.delay(post_id)
    return new_status
