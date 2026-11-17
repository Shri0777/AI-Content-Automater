"""Start making posts, and let users find, approve and reject them."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from kombu.exceptions import OperationalError

from core.errors import AppError
from credentials.services import require_credential
from planning.models import PostSlot
from planning.services import get_plan
from publishing.tasks import publish_post_task
from quotas.services import use_daily_quota
from studio.files import read_artwork, read_poster, save_poster
from studio.models import Post, PostVersion
from studio.pipeline import poster_for
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
    posts = Post.objects.filter(user=user).select_related("plan", "topic", "slot")
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
    for kind in ["text", "image"]:
        if require_credential(user, kind).status == "invalid":
            raise PlanCannotGenerate(
                f"Your {kind} provider refused its API key. "
                "Update the key on the credentials page first."
            )
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


class PostNotEditable(AppError):
    """Raised when a post is past the point where it can be edited."""

    status = 409
    code = "post_not_editable"
    title = "Post cannot be edited"


class SlotAlreadyStarted(AppError):
    """Raised when another worker started this slot first."""

    status = 409
    code = "slot_already_started"
    title = "Already started"


def create_scheduled_post(slot):
    """Create the post for a claimed slot and start making it.

    The quota is used and the slot marked "started" in the same transaction
    as the post is created, so either all of it happens or none of it.
    """
    plan = slot.plan
    topic = choose_topic(plan)
    with transaction.atomic():
        use_daily_quota(plan.user, "posts_per_day")
        use_daily_quota(plan.user, "posts_per_plan_per_day", scope=str(plan.id))
        post = Post.objects.create(
            user=plan.user,
            plan=plan,
            topic=topic,
            slot=slot,
            demo_mode=settings.DEMO_MODE,
        )
        started = PostSlot.objects.filter(id=slot.id, status="claimed").update(
            status="started", claimed_until=None
        )
        if started == 0:
            raise SlotAlreadyStarted("Another worker started this slot first.")
    queue_post_job(advance_post_task, post)
    return post


def edit_post(user, post_id, headline, caption):
    """Save the user's own wording as a new version, on the same artwork.

    Only a post waiting for approval can be edited. The user's version is
    the one shown and published from then on (Post.final_version).
    """
    post = get_post(user, post_id)
    if post.status != "awaiting_approval":
        raise PostNotEditable("Only a post waiting for your approval can be edited.")
    current = post.final_version()
    edited = PostVersion.objects.create(
        post=post,
        number=post.latest_version().number + 1,
        headline=headline or current.headline,
        caption=caption,
        image_prompt=current.image_prompt,
        artwork_path=current.artwork_path,
        edited_by_user=True,
    )
    edited.poster_path = save_poster(
        edited, poster_for(post, edited, read_artwork(current))
    )
    edited.save(update_fields=["poster_path"])
    return get_post(user, post.id)


def approve_post(user, post_id):
    """Approve a post that is waiting, and publish it when its time comes.

    A scheduled post whose time is still ahead is published by the
    scheduler at that time (publishing/scheduled.py); any other post is
    published straight away.
    """
    post = get_post(user, post_id)
    change_status(post, "approved")
    if post.slot is None or post.slot.publish_at <= timezone.now():
        queue_post_job(publish_post_task, post)
    return get_post(user, post.id)


def reject_post(user, post_id):
    """Reject a post that is waiting, so it is never published."""
    post = get_post(user, post_id)
    change_status(post, "rejected")
    return post


def get_poster_bytes(user, post_id):
    """Return the PNG bytes of a post's newest poster."""
    version = get_post(user, post_id).final_version()
    if version is None or not version.poster_path:
        raise PostNotFound("This post has no poster yet.")
    return read_poster(version)


def count_awaiting_approval(user):
    """Return how many of the user's posts wait for approval."""
    return Post.objects.filter(user=user, status="awaiting_approval").count()
