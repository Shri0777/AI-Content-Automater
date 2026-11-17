"""Delete old poster images and old pipeline records (run nightly).

Poster images are the biggest files we keep. After each user's
poster_retention_days (30 by default) the poster and artwork files are
deleted and the version is marked image_expired; its headline, caption,
review and publications stay as the user's history.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage

from quotas.services import get_limit
from studio.models import GenerationStep, PostVersion

STEP_RETENTION = timedelta(days=90)


def delete_file(path):
    """Delete a stored file if it is there."""
    if path and default_storage.exists(path):
        default_storage.delete(path)


def expire_images_of(user, now):
    """Delete the user's poster files older than their retention; return how many."""
    days = get_limit(user, "poster_retention_days")
    old_versions = PostVersion.objects.filter(
        post__user=user, image_expired=False, created_at__lt=now - timedelta(days=days)
    )
    count = 0
    for version in old_versions:
        delete_file(version.poster_path)
        delete_file(version.artwork_path)
        version.poster_path = ""
        version.artwork_path = ""
        version.image_expired = True
        version.save(update_fields=["poster_path", "artwork_path", "image_expired"])
        count = count + 1
    return count


def expire_old_images(now):
    """Expire old poster images for every user who has some; return how many."""
    user_ids = (
        PostVersion.objects.filter(image_expired=False)
        .values_list("post__user_id", flat=True)
        .distinct()
    )
    count = 0
    for user in get_user_model().objects.filter(id__in=list(user_ids)):
        count = count + expire_images_of(user, now)
    return count


def delete_old_steps(now):
    """Delete pipeline step records older than STEP_RETENTION; return how many."""
    deleted, _ = GenerationStep.objects.filter(
        created_at__lt=now - STEP_RETENTION
    ).delete()
    return deleted
