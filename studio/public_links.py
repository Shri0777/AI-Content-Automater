"""Signed public links to poster images, for services that download them.

Buffer (and later Instagram) will not accept an uploaded image; it downloads
the poster from an address on the internet. These links need no login, so
each one carries a signature made with our SECRET_KEY: it cannot be guessed
or changed to point at another poster, and it stops working after
LINK_LIFETIME.
"""

from datetime import timedelta

from django.conf import settings
from django.core import signing

from core.errors import AppError
from studio.files import read_poster
from studio.models import PostVersion

# Long enough for a scheduled post to go out after it was queued.
LINK_LIFETIME = timedelta(days=7)
# Keeps these signatures separate from any other use of SECRET_KEY.
SIGNING_SALT = "studio.public-poster"


class PublicPosterNotFound(AppError):
    """Raised for a link that is damaged, expired or for a missing poster."""

    status = 404
    code = "not_found"
    title = "Not found"


def make_public_poster_url(version):
    """Return a signed, login-free address of version's poster image."""
    token = signing.dumps(str(version.id), salt=SIGNING_SALT)
    return f"{settings.PUBLIC_API_URL}/api/v1/public/posters/{token}.png"


def read_public_poster(token):
    """Return the PNG bytes behind a signed link, or raise PublicPosterNotFound."""
    try:
        version_id = signing.loads(token, salt=SIGNING_SALT, max_age=LINK_LIFETIME)
    except signing.BadSignature:
        # An expired link raises SignatureExpired, a kind of BadSignature.
        raise PublicPosterNotFound("This poster link is not valid.") from None
    version = PostVersion.objects.filter(id=version_id).first()
    if version is None or not version.poster_path:
        raise PublicPosterNotFound("This poster no longer exists.")
    return read_poster(version)
