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


def fit_lines(draw, lines, font, max_width, max_lines):
    """Keep at most max_lines; end the last kept line with "…" if some were cut."""
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1]
    while last and draw.textlength(f"{last}…", font=font) > max_width:
        last = last[:-1]
    kept[-1] = f"{last.rstrip()}…"
    return kept


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


def fit_artwork(artwork_bytes, width, height):
    """Return the artwork as PNG bytes, cropped and scaled to width x height."""
    return to_png_bytes(open_artwork(artwork_bytes, width, height).convert("RGB"))


def shade_lower_part(image, shade_top):
    """Return image with everything below shade_top darkened, for readable text."""
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle(
        [0, shade_top, image.width, image.height], fill=SHADE
    )
    return Image.alpha_composite(image, shade)


def render_poster(artwork_bytes, headline, source_line, width, height):
    """Return width x height PNG bytes: artwork with the headline on top.

    Text stays inside a margin on every side (the "safe area"), and the
    headline gets only as many lines as fit above the source line.
    """
    margin = min(width, height) // 18
    shade_top = height * 55 // 100
    image = shade_lower_part(open_artwork(artwork_bytes, width, height), shade_top)
    draw = ImageDraw.Draw(image)
    headline_font = ImageFont.load_default(size=height // 15)
    source_font = ImageFont.load_default(size=height // 40)
    line_height = height // 13
    # Measured, not guessed, so the source line ends exactly at the margin.
    source_box = draw.textbbox((0, 0), source_line, font=source_font)
    source_y = height - margin - source_box[3]
    y = shade_top + margin // 2
    room = source_y - margin // 2 - y
    max_lines = max(1, min(MAX_HEADLINE_LINES, room // line_height))
    lines = wrap_text(draw, headline, headline_font, width - 2 * margin)
    for line in fit_lines(draw, lines, headline_font, width - 2 * margin, max_lines):
        draw.text((margin, y), line, font=headline_font, fill=WHITE)
        y = y + line_height
    draw.text((margin, source_y), source_line, font=source_font, fill=LIGHT_GREY)
    return to_png_bytes(image.convert("RGB"))
