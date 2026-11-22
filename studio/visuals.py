"""Draw and save a version's slides and its share image.

The pipeline (studio/pipeline.py), corrections and the user's own edits
(studio/services.py) all call save_visuals(), so every version is drawn the
same way: the plan's brand colour, the topic's name on the cover, and the
AI artwork only if the plan asked for it (its bytes are passed in, or b"").
"""

from studio.files import read_artwork, save_poster, save_slide
from studio.palette import palette_for
from studio.slide_parts import Deck
from studio.slides import render_share_image, render_slides

# Portrait slides for carousels and LinkedIn documents (4:5).
SLIDE_SIZE = (1080, 1350)
# The one square image for platforms that show a single picture.
SHARE_SIZE = (1080, 1080)


def deck_for(post, version, artwork):
    """Return the Deck of words and colours for a version's slides."""
    source_name = ""
    if post.article is not None:
        source_name = post.article.source_name
    kicker = ""
    if post.topic is not None:
        kicker = post.topic.name
    return Deck(
        headline=version.headline,
        palette=palette_for(post.plan.brand_colour),
        source_name=source_name,
        kicker=kicker,
        points=version.points,
        figure=version.figure or {},
        quote=version.quote or {},
        takeaway=version.takeaway,
        artwork=artwork,
    )


def save_visuals(post, version, artwork):
    """Draw and save the version's slides and share image, and their paths."""
    deck = deck_for(post, version, artwork)
    paths = []
    slides = render_slides(deck, SLIDE_SIZE[0], SLIDE_SIZE[1])
    for number, png in enumerate(slides, start=1):
        paths.append(save_slide(version, number, png))
    share_image = render_share_image(deck, SHARE_SIZE[0], SHARE_SIZE[1])
    version.slide_paths = paths
    version.poster_path = save_poster(version, share_image)
    version.save(update_fields=["slide_paths", "poster_path"])


def artwork_of(version):
    """Return the version's saved AI artwork, or b"" if it has none."""
    if not version.artwork_path:
        return b""
    return read_artwork(version)
