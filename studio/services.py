"""Start making posts, and let users find, approve and reject them."""

from django.conf import settings
from django.db import transaction
from kombu.exceptions import OperationalError

from core.errors import AppError
from credentials.services import require_credential
from planning.services import get_plan
from publishing.tasks import publish_post_task
from quotas.services import use_daily_quota
from studio.files import read_poster
from studio.models import Post
from studio.statuses import change_status, fail_after_crash
from studio.tasks import advance_post_task


class PostNotFound(AppError):
    """Raised when a post (or its poster) does not exist or is not the user's."""

    status = 404
    code = "not_found"
    title = "Not found"


class PlanCannotGenerate(AppError):
    """Raised when a plan is not able to make a post right now."""

    status = 400
    code = "plan_cannot_generate"
    title = "Plan cannot make a post"


class JobsUnavailable(AppError):
    """Raised when background jobs cannot be queued (the queue is down)."""

    status = 503
    code = "jobs_unavailable"
    title = "Background jobs unavailable"


JOBS_DOWN_REASON = (
    "Background jobs were not running, so this post could not continue. "
    "Please try again in a few minutes."
)


def queue_post_job(task, post):
    """Queue a background job for post. If the queue is down, fail the post.

    Without this, the post would wait forever for a job that never comes.
    """
    try:
        task.delay(str(post.id))
    except OperationalError:
        fail_after_crash(post.id, JOBS_DOWN_REASON)
        raise JobsUnavailable(JOBS_DOWN_REASON) from None


def get_posts(user, status=""):
    """Return the user's posts, optionally only those with one status."""
    posts = Post.objects.filter(user=user).select_related("plan", "topic")
    if status:
        posts = posts.filter(status=status)
    return posts


def get_post(user, post_id):
    """Return one of the user's posts, or raise PostNotFound."""
    post = get_posts(user).filter(id=post_id).first()
    if post is None:
        raise PostNotFound("That post does not exist.")
    return post


def choose_topic(plan):
    """Return the plan's topic with the fewest posts so far (oldest first)."""
    best_topic = None
    best_count = 0
    for topic in plan.topics.all():
        count = topic.posts.count()
        if best_topic is None or count < best_count:
            best_topic = topic
            best_count = count
    if best_topic is None:
        raise PlanCannotGenerate("Add a topic to this plan first.")
    return best_topic


def start_generation(user, plan_id):
    """Create a post for the plan and start making it in the background."""
    plan = get_plan(user, plan_id)
    if plan.paused:
        raise PlanCannotGenerate("This plan is paused. Resume it first.")
    require_credential(user, "text")
    require_credential(user, "image")
    topic = choose_topic(plan)
    # If any limit is reached, the whole block is undone, so no use is
    # counted for a post that was never made.
    with transaction.atomic():
        use_daily_quota(user, "generate_now_per_day")
        use_daily_quota(user, "posts_per_day")
        use_daily_quota(user, "posts_per_plan_per_day", scope=str(plan.id))
        post = Post.objects.create(
            user=user, plan=plan, topic=topic, demo_mode=settings.DEMO_MODE
        )
    queue_post_job(advance_post_task, post)
    return get_post(user, post.id)


def approve_post(user, post_id):
    """Approve a post that is waiting, and start publishing it."""
    post = get_post(user, post_id)
    change_status(post, "approved")
    queue_post_job(publish_post_task, post)
    return get_post(user, post.id)


def reject_post(user, post_id):
    """Reject a post that is waiting, so it is never published."""
    post = get_post(user, post_id)
    change_status(post, "rejected")
    return post


def get_poster_bytes(user, post_id):
    """Return the PNG bytes of a post's newest poster."""
    version = get_post(user, post_id).latest_version()
    if version is None or not version.poster_path:
        raise PostNotFound("This post has no poster yet.")
    return read_poster(version)


def count_awaiting_approval(user):
    """Return how many of the user's posts wait for approval."""
    return Post.objects.filter(user=user, status="awaiting_approval").count()
