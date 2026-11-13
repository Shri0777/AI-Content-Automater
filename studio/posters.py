"""Draw poster images. This is the only file that uses the Pillow library.

render_poster() puts the headline and source line on top of AI artwork. The
AI never draws words itself, so the text is always crisp and spelled right.
draw_abstract_artwork() makes simple artwork from a piece of text; the demo
image model uses it in place of a real AI image.
"""

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from core.errors import ProviderError

WHITE = (255, 255, 255, 255)
LIGHT_GREY = (220, 220, 220, 255)
# Black at about two-thirds strength, so text stays readable on any artwork.
SHADE = (0, 0, 0, 170)
MAX_HEADLINE_LINES = 4


def to_png_bytes(image):
    """Return image saved as PNG bytes."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def draw_abstract_artwork(seed_text, width, height):
    """Return PNG bytes of a gradient with circles, chosen by seed_text.

    The same seed_text always gives the same picture.
    """
    digest = hashlib.sha256(seed_text.encode()).digest()
    top = (digest[0], digest[1], digest[2])
    bottom = (digest[3], digest[4], digest[5])
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        share = y / height
        colour = []
        for channel in range(3):
            colour.append(int(top[channel] * (1 - share) + bottom[channel] * share))
        draw.line([(0, y), (width, y)], fill=tuple(colour))
    for index in range(5):
        x = digest[6 + index] * width // 255
        y = digest[11 + index] * height // 255
        radius = 40 + digest[16 + index] * width // 1020
        box = [x - radius, y - radius, x + radius, y + radius]
        draw.ellipse(box, outline=WHITE, width=6)
    return to_png_bytes(image)


def wrap_text(draw, text, font, max_width):
    """Split text into lines that each fit within max_width pixels."""
    lines = []
    current = ""
    for word in text.split():
        candidate = word if current == "" else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width or current == "":
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def open_artwork(artwork_bytes, width, height):
    """Return the artwork cropped and scaled to exactly width x height.

    Image models return their own sizes and shapes; the middle of the
    artwork is kept and the edges trimmed, so it is never stretched.
    """
    try:
        artwork = Image.open(BytesIO(artwork_bytes))
        artwork.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise ProviderError(
            "The image model sent back something that is not an image."
        ) from None
    return ImageOps.fit(artwork.convert("RGBA"), (width, height))


def render_poster(artwork_bytes, headline, source_line, width, height):
    """Return width x height PNG bytes: artwork with the headline on top."""
    image = open_artwork(artwork_bytes, width, height)
    margin = width // 18
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shade_top = height * 55 // 100
    ImageDraw.Draw(shade).rectangle([0, shade_top, width, height], fill=SHADE)
    image = Image.alpha_composite(image, shade)
    draw = ImageDraw.Draw(image)
    headline_font = ImageFont.load_default(size=height // 15)
    source_font = ImageFont.load_default(size=height // 40)
    lines = wrap_text(draw, headline, headline_font, width - 2 * margin)
    y = shade_top + margin
    for line in lines[:MAX_HEADLINE_LINES]:
        draw.text((margin, y), line, font=headline_font, fill=WHITE)
        y = y + height // 13
    source_y = height - margin - height // 40
    draw.text((margin, source_y), source_line, font=source_font, fill=LIGHT_GREY)
    return to_png_bytes(image.convert("RGB"))
