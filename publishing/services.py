"""Publish approved posts to the plan's social accounts.

A "generate now" post is published as soon as it is approved. A scheduled
post is published at its slot's time by publishing/scheduled.py.
"""

import hashlib

from django.utils import timezone

from core.errors import ProviderError, ProviderKeyRejected, ProviderNoAnswer
from notifications.services import notify
from publishing.models import Publication
from social.platforms import caption_limit_for, get_publisher
from social.publishers import PostContent
from social.tokens import REFRESH_BEFORE_POSTING, mark_needs_reauth, refresh_account
from studio.files import read_poster
from studio.models import Post
from studio.public_links import make_public_poster_url
from studio.statuses import StatusChangeNotAllowed, change_status

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
    return add_ai_label(version.caption, label, caption_limit_for(account))


def send_to_platform(post, version, account, poster):
    """Refresh the account's token if needed, then post; return the post id."""
    account = refresh_account(account.id, REFRESH_BEFORE_POSTING)
    if account.status != "active":
        raise ProviderError(f"{account.display_name} must be connected again.")
    content = PostContent(
        caption_for(post, version, account), poster, make_public_poster_url(version)
    )
    try:
        return get_publisher(account.platform).publish(account, content)
    except ProviderKeyRejected:
        mark_needs_reauth(account, "The platform refused this account's token.")
        raise


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
    send_and_record(publication, post, version, account, poster)
    return publication


def send_and_record(publication, post, version, account, poster):
    """Send the post to the platform and save how it went on publication."""
    try:
        publication.external_id = send_to_platform(post, version, account, poster)
    except ProviderNoAnswer as error:
        # It may have gone out: never send it again on our own.
        publication.status = "ambiguous"
        publication.error = str(error)
    except ProviderError as error:
        publication.status = "failed"
        publication.error = str(error)
    else:
        publication.status = "published"
        publication.published_at = timezone.now()
    publication.save()


def names_with_status(publications, status):
    """Return the account names of the publications with this status."""
    names = []
    for publication in publications:
        if publication.status == status:
            names.append(publication.account_name())
    return names


def tell_owner_unconfirmed(post, names):
    """Tell the owner once that some accounts did not confirm the post."""
    notify(
        post.user,
        "publish_unconfirmed",
        f"We could not confirm the post reached: {', '.join(names)}. "
        "Please check those accounts, then tell us what you see.",
        related=post,
        dedupe_key=f"unconfirmed:{post.id}",
    )


def partly_published_reason(failed, unconfirmed):
    """Return a note naming accounts that failed or are not confirmed yet."""
    parts = []
    if failed:
        parts.append(f"Could not publish to: {', '.join(failed)}.")
    if unconfirmed:
        parts.append(f"Not confirmed yet: {', '.join(unconfirmed)}.")
    return " ".join(parts)


def finish_post(post, publications):
    """Settle the post's status from how its publications went.

    Published to any account: "published". Only unconfirmed ones left: the
    post stays "publishing" until they are settled. Otherwise: "failed".
    """
    if names_with_status(publications, "publishing"):
        # Another worker is still sending to an account; it finishes the post.
        return
    published = names_with_status(publications, "published")
    unconfirmed = names_with_status(publications, "ambiguous")
    failed = names_with_status(publications, "failed")
    if unconfirmed:
        tell_owner_unconfirmed(post, unconfirmed)
    if published:
        reason = partly_published_reason(failed, unconfirmed)
        if move_once(post, "published", reason):
            notify(post.user, "post_published", "Your post is live.", related=post)
    elif not unconfirmed:
        reason = "The post could not be published to any of its accounts."
        if move_once(post, "failed", reason):
            notify(post.user, "post_failed", reason, related=post)


def move_once(post, new_status, reason):
    """Change the post's status; return False if another worker did it first.

    Two workers can publish the same post at once. Only one contacts each
    platform, but both reach this point; the second must stop quietly.
    """
    try:
        change_status(post, new_status, reason)
    except StatusChangeNotAllowed:
        return False
    return True


def fail_for_missing_poster(post):
    """Fail a post whose poster was deleted after the retention period."""
    reason = "The poster was deleted after the retention period."
    if move_once(post, "failed", reason):
        notify(post.user, "post_failed", reason, related=post)


def publish_post(post_id):
    """Publish an approved post to every active account of its plan.

    Returns the post's new status, or "deleted" if the post no longer exists.
    """
    post = Post.objects.select_related("plan", "user").filter(id=post_id).first()
    if post is None:
        return "deleted"
    if post.status == "approved" and not move_once(post, "publishing", ""):
        # Another worker started publishing it a moment ago.
        post.refresh_from_db()
    if post.status != "publishing":
        return post.status
    version = post.final_version()
    if version.image_expired or not version.poster_path:
        fail_for_missing_poster(post)
        return post.status
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
