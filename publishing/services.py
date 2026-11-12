"""Publish approved posts to the plan's social accounts.

For now an approved post is published straight away. Publishing at a
scheduled time arrives with schedules in Phase 5.
"""

import hashlib

from django.utils import timezone

from core.errors import ProviderError
from notifications.services import notify
from publishing.models import Publication
from social.models import CAPTION_LIMITS
from social.services import get_publisher
from studio.files import read_poster
from studio.models import Post
from studio.statuses import change_status

ELLIPSIS = "…"


def add_ai_label(caption, label, max_length):
    """Return caption with label added, all within max_length characters.

    The caption is shortened first, so the label itself is never cut off.
    An empty label adds nothing.
    """
    if label == "":
        return caption[:max_length]
    room_for_caption = max_length - len(label) - 2
    if len(caption) > room_for_caption:
        caption = caption[: room_for_caption - 1].rstrip() + ELLIPSIS
    return f"{caption}\n\n{label}"


def make_idempotency_key(post, version, account):
    """Return the same key every time for this post, version and account."""
    text = f"{post.id}:{version.id}:{account.id}"
    return hashlib.sha256(text.encode()).hexdigest()


def caption_for(post, version, account):
    """Return the caption to send, with the plan's AI label if it is on."""
    label = ""
    if post.plan.ai_label_enabled:
        label = post.plan.ai_label_text
    return add_ai_label(version.caption, label, CAPTION_LIMITS[account.platform])


def publish_to_account(post, version, account, poster):
    """Publish to one account and return the Publication.

    Only the first attempt for a key contacts the platform. If a record
    already exists, an earlier attempt may have reached the platform, and
    a missing post is better than a duplicate one.
    """
    publication, created = Publication.objects.get_or_create(
        idempotency_key=make_idempotency_key(post, version, account),
        defaults={
            "post": post,
            "version": version,
            "account": account,
            "demo_mode": post.demo_mode,
        },
    )
    if not created:
        return publication
    publisher = get_publisher(account.platform)
    try:
        caption = caption_for(post, version, account)
        publication.external_id = publisher.publish(account, caption, poster)
    except ProviderError as error:
        publication.status = "failed"
        publication.error = str(error)
    else:
        publication.status = "published"
        publication.published_at = timezone.now()
    publication.save()
    return publication


def finish_post(post, publications):
    """Mark the post published if any account got it, otherwise failed."""
    failed_names = []
    for publication in publications:
        if publication.status != "published":
            failed_names.append(publication.account.display_name)
    if len(failed_names) < len(publications):
        reason = ""
        if failed_names:
            reason = f"Could not publish to: {', '.join(failed_names)}."
        change_status(post, "published", reason)
        notify(post.user, "post_published", "Your post is live.", related=post)
        return
    reason = "The post could not be published to any of its accounts."
    change_status(post, "failed", reason)
    notify(post.user, "post_failed", reason, related=post)


def publish_post(post_id):
    """Publish an approved post to every active account of its plan.

    Returns the post's new status, or "deleted" if the post no longer exists.
    """
    post = Post.objects.select_related("plan", "user").filter(id=post_id).first()
    if post is None:
        return "deleted"
    if post.status == "approved":
        change_status(post, "publishing")
    if post.status != "publishing":
        return post.status
    version = post.latest_version()
    poster = read_poster(version)
    publications = []
    for account in post.plan.accounts.filter(status="active"):
        publications.append(publish_to_account(post, version, account, poster))
    if not publications:
        reason = "The plan has no active social accounts to publish to."
        change_status(post, "failed", reason)
        notify(post.user, "post_failed", reason, related=post)
        return post.status
    finish_post(post, publications)
    return post.status
