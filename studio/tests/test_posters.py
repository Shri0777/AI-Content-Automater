"""Posters look the same as the approved reference ("golden") images.

The reference images live in studio/tests/golden/. After a deliberate
change to the poster design, look at the new posters, then save them as
the new references with:

    UPDATE_GOLDEN_IMAGES=1 uv run pytest studio/tests/test_posters.py
"""

import os
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont

from studio.posters import draw_abstract_artwork, fit_lines, render_poster, wrap_text

GOLDEN_FOLDER = Path(__file__).parent / "golden"
SIZES = [(1080, 1080), (1200, 675), (1080, 1350)]
HEADLINES = {
    "short": "Small model, big summaries",
    "long": "A very long headline about a company that announced several new "
    "things today, and then several more things, and then even more news",
}
SOURCE_LINE = "Source: Example News"
# A pixel counts as different if any colour channel moved more than this.
PIXEL_TOLERANCE = 24
# At most this share of pixels may differ (font smoothing can vary a little).
MAX_DIFFERENT_SHARE = 0.002


def poster(width, height, headline, artwork=None):
    """Return a rendered poster as a Pillow image."""
    if artwork is None:
        artwork = draw_abstract_artwork("golden", width, height)
    png = render_poster(artwork, headline, SOURCE_LINE, width, height)
    return Image.open(BytesIO(png)).convert("RGB")


def plain_artwork(width, height, colour):
    """Return PNG bytes of a single-colour picture."""
    buffer = BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def mark_if_different(value):
    """Return 255 for a pixel difference above PIXEL_TOLERANCE, else 0."""
    if value > PIXEL_TOLERANCE:
        return 255
    return 0


def mark_if_light(value):
    """Return 255 for a light pixel (text on black), else 0."""
    if value > 100:
        return 255
    return 0


def share_of_different_pixels(first, second):
    """Return the share of pixels that differ by more than PIXEL_TOLERANCE."""
    difference = ImageChops.difference(first, second).convert("L")
    different = difference.point(mark_if_different)
    return different.histogram()[255] / (first.width * first.height)


@pytest.mark.parametrize("width, height", SIZES)
@pytest.mark.parametrize("length", list(HEADLINES))
def test_a_poster_matches_its_reference_image(width, height, length):
    image = poster(width, height, HEADLINES[length])
    golden_path = GOLDEN_FOLDER / f"poster_{width}x{height}_{length}.png"
    if os.environ.get("UPDATE_GOLDEN_IMAGES") == "1":
        GOLDEN_FOLDER.mkdir(exist_ok=True)
        image.save(golden_path)
    golden = Image.open(golden_path).convert("RGB")

    assert image.size == golden.size
    assert share_of_different_pixels(image, golden) <= MAX_DIFFERENT_SHARE


@pytest.mark.parametrize("width, height", SIZES)
def test_all_text_stays_inside_the_safe_area(width, height):
    # On black artwork, every light pixel is text.
    black = plain_artwork(width, height, (0, 0, 0))
    image = poster(width, height, HEADLINES["long"], artwork=black).convert("L")
    light = image.point(mark_if_light)

    left, top, right, bottom = light.getbbox()

    margin = min(width, height) // 18
    assert left >= margin - 2
    assert right <= width - margin + 2
    assert bottom <= height - margin + 2
    assert top >= height // 2


def relative_luminance(rgb):
    """Return the WCAG relative luminance of an (r, g, b) colour."""
    channels = []
    for value in rgb:
        share = value / 255
        if share <= 0.03928:
            channels.append(share / 12.92)
        else:
            channels.append(((share + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


@pytest.mark.parametrize("width, height", SIZES)
def test_text_is_readable_even_on_pure_white_artwork(width, height):
    white = plain_artwork(width, height, (255, 255, 255))
    image = poster(width, height, "Hi", artwork=white)
    behind_text = image.getpixel((width - 5, height - 5))

    lighter = relative_luminance((255, 255, 255)) + 0.05
    darker = relative_luminance(behind_text) + 0.05
    # WCAG AA asks for at least 4.5 : 1 for normal text.
    assert lighter / darker >= 4.5


def test_a_headline_too_long_to_fit_ends_with_an_ellipsis_not_cut_words():
    draw = ImageDraw.Draw(Image.new("RGB", (400, 400)))
    font = ImageFont.load_default(size=30)
    lines = wrap_text(draw, HEADLINES["long"], font, 300)

    kept = fit_lines(draw, lines, font, 300, 2)

    assert len(kept) == 2
    assert kept[-1].endswith("…")
    assert draw.textlength(kept[-1], font=font) <= 300
