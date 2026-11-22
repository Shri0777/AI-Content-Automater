"""Save and read poster, slide and artwork image files.

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


def save_artwork(version, png_bytes):
    """Save a version's text-free artwork and return where it was saved."""
    post = version.post
    path = f"posters/{post.user_id}/{post.id}/v{version.number}-artwork.png"
    return default_storage.save(path, ContentFile(png_bytes))


def read_artwork(version):
    """Return the artwork bytes of a version."""
    with default_storage.open(version.artwork_path, "rb") as artwork_file:
        return artwork_file.read()


def read_poster(version):
    """Return the poster image bytes of a version."""
    with default_storage.open(version.poster_path, "rb") as poster_file:
        return poster_file.read()


def save_slide(version, number, png_bytes):
    """Save one slide (number 1 is the cover) and return where it was saved."""
    post = version.post
    path = f"posters/{post.user_id}/{post.id}/v{version.number}-slide{number}.png"
    return default_storage.save(path, ContentFile(png_bytes))


def read_slide(version, number):
    """Return the image bytes of a version's slide (number 1 is the cover)."""
    with default_storage.open(version.slide_paths[number - 1], "rb") as slide_file:
        return slide_file.read()


def read_slides(version):
    """Return the image bytes of every slide of a version, in order."""
    slides = []
    for number in range(1, len(version.slide_paths) + 1):
        slides.append(read_slide(version, number))
    return slides
