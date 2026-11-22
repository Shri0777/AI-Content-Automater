"""Settle publications whose outcome is unknown ("ambiguous").

When a platform takes a post but never answers, we cannot know if it went
out. Sending it again could post it twice, and a duplicate is worse than a
missing post, so it is never sent again automatically. Instead:

1. Every 10 minutes, reconcile_ambiguous() asks each platform (through its
   publisher's check_status) what happened.
2. If the platform cannot tell, the owner is asked once (a notification),
   and settles it with POST /api/v1/publications/<id>/resolve/.

A send whose worker crashed halfway is left marked "publishing"; after
STUCK_AFTER it is treated as unconfirmed too.
"""

from datetime import timedelta

from django.utils import timezone

from core.errors import AppError, ProviderError
from notifications.services import notify
from publishing.models import Publication
from publishing.services import finish_post
from social.platforms import publisher_for_account

# Give the platform a moment before asking it what happened.
CHECK_AFTER = timedelta(minutes=2)
# A send still marked "publishing" after this long means its worker stopped
# halfway (a crash or restart); it may have gone out, so it is unconfirmed.
STUCK_AFTER = timedelta(minutes=10)


class PublicationNotFound(AppError):
    """Raised for a publication that does not exist or is not the user's."""

    status = 404
    code = "not_found"
    title = "Not found"


class PublicationAlreadySettled(AppError):
    """Raised when a publication's outcome is already known."""

    status = 409
    code = "already_settled"
    title = "Already settled"


def settle(publication, outcome, settled_by, external_id=""):
    """Record the outcome of an ambiguous publication and update its post."""
    publication.status = "published" if outcome == "published" else "failed"
    publication.resolved_by = settled_by
    publication.checked_at = timezone.now()
    if outcome == "published":
        publication.external_id = external_id or publication.external_id
        publication.published_at = publication.published_at or timezone.now()
    else:
        publication.error = "It did not go out (checked after no answer)."
    publication.save()
    post = publication.post
    publications = list(post.publications.select_related("account"))
    if post.status == "publishing" and not has_ambiguous(publications):
        finish_post(post, publications)


def has_ambiguous(publications):
    """Return True if any of the publications is still unconfirmed."""
    for publication in publications:
        if publication.status == "ambiguous":
            return True
    return False


def ask_platform(publication):
    """Return the platform's outcome for an ambiguous publication."""
    if publication.account is None:
        return {"outcome": "unknown", "external_id": ""}
    publisher = publisher_for_account(publication.account)
    try:
        return publisher.check_status(publication.account, publication)
    except ProviderError:
        return {"outcome": "unknown", "external_id": ""}


def reconcile_publication(publication):
    """Settle one ambiguous publication if its platform knows; return the outcome."""
    answer = ask_platform(publication)
    if answer["outcome"] in ["published", "not_published"]:
        settle(
            publication, answer["outcome"], "platform", answer.get("external_id", "")
        )
        return answer["outcome"]
    publication.checked_at = timezone.now()
    publication.save(update_fields=["checked_at"])
    notify(
        publication.post.user,
        "publish_unconfirmed",
        f"We still cannot tell whether your post reached "
        f"{publication.account_name()}. Please check it and tell us.",
        related=publication.post,
        dedupe_key=f"unconfirmed:{publication.post_id}",
    )
    return "unknown"


def reconcile_ambiguous(now=None):
    """Try to settle every ambiguous publication; return how many were settled."""
    if now is None:
        now = timezone.now()
    Publication.objects.filter(
        status="publishing", created_at__lte=now - STUCK_AFTER
    ).update(
        status="ambiguous",
        error="The worker stopped while sending, so it may have gone out.",
    )
    waiting = Publication.objects.filter(
        status="ambiguous", created_at__lte=now - CHECK_AFTER
    ).select_related("post", "post__user", "account")
    settled = 0
    for publication in waiting:
        if reconcile_publication(publication) != "unknown":
            settled = settled + 1
    return settled


def resolve_publication(user, publication_id, outcome, external_id=""):
    """Let the owner say whether an unconfirmed post went out."""
    publication = Publication.objects.filter(id=publication_id, post__user=user).first()
    if publication is None:
        raise PublicationNotFound("That publication does not exist.")
    if publication.status != "ambiguous":
        raise PublicationAlreadySettled("This publication's outcome is already known.")
    settle(publication, outcome, "user", external_id)
    return publication
