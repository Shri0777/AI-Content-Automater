"""Save and read poster image files.

Files go through Django's file storage, which is a folder on disk
(MEDIA_ROOT) for now. S3-compatible storage can be swapped in later
without changing this file's callers.
"""

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def save_poster(version, png_bytes):
    """Save a version's poster image and return where it was saved."""
    post = version.post
    path = f"posters/{post.user_id}/{post.id}/v{version.number}.png"
    return default_storage.save(path, ContentFile(png_bytes))


def read_poster(version):
    """Return the poster image bytes of a version."""
    with default_storage.open(version.poster_path, "rb") as poster_file:
        return poster_file.read()
