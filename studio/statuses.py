"""The one table of allowed post status changes, and the function that uses it.

Every status change goes through change_status(), so a post can never jump
somewhere it should not (for example from "failed" straight to "published").
The tests read the same table.
"""

from django.utils import timezone

from core.errors import AppError
from notifications.services import notify
from studio.models import Post

ALLOWED_TRANSITIONS = {
    "researching": ["drafting", "skipped", "failed"],
    "drafting": ["imaging", "failed"],
    "imaging": ["reviewing", "failed"],
    "reviewing": ["awaiting_approval", "failed"],
    # A scheduled post expires if nobody approves it in time.
    "awaiting_approval": ["approved", "rejected", "expired"],
    # An approved post fails if publishing cannot even start.
    "approved": ["publishing", "failed"],
    "publishing": ["published", "failed"],
    # Finished: nothing comes after these.
    "published": [],
    "rejected": [],
    "expired": [],
    "skipped": [],
    "failed": [],
}


CRASH_REASON = (
    "An unexpected error stopped this post. "
    "It has been logged so the problem can be fixed."
)


class StatusChangeNotAllowed(AppError):
    """Raised when a post cannot move to the requested status."""

    status = 409
    code = "status_conflict"
    title = "Post cannot change like that"


def change_status(post, new_status, reason=""):
    """Move post to new_status, or raise StatusChangeNotAllowed."""
    if new_status not in ALLOWED_TRANSITIONS[post.status]:
        raise StatusChangeNotAllowed(
            f"A post that is '{post.status}' cannot become '{new_status}'."
        )
    # The UPDATE only matches while the post still has its old status, so if
    # two requests (say, two clicks on "approve") race, only one wins.
    updated_rows = Post.objects.filter(id=post.id, status=post.status).update(
        status=new_status, status_reason=reason, updated_at=timezone.now()
    )
    if updated_rows == 0:
        raise StatusChangeNotAllowed(
            "Someone else changed this post just now. Reload it and try again."
        )
    post.status = new_status
    post.status_reason = reason


def fail_after_crash(post_id, reason=CRASH_REASON):
    """Mark a post failed after its background job crashed or never started.

    Returns True if the post was marked failed. A post that was deleted,
    already finished, or waits for the user is left alone.
    """
    post = Post.objects.select_related("user").filter(id=post_id).first()
    if post is None or "failed" not in ALLOWED_TRANSITIONS[post.status]:
        return False
    change_status(post, "failed", reason)
    notify(post.user, "post_failed", reason, related=post)
    return True
