"""Drawing helpers shared by the slides (studio/slides.py lays them out).

Only this file and studio/slides.py use the Pillow library. The AI never
draws words itself: all text is drawn here, so it is crisp and spelled
right. draw_abstract_artwork() makes simple artwork from a piece of text;
the demo image model uses it in place of a real AI image.
"""

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from core.errors import ProviderError

WHITE = (255, 255, 255, 255)
# Inter (studio/fonts/README.md): it has accented letters, dashes and
# currency signs, which Pillow's built-in font draws as boxes.
FONT_FILE = Path(__file__).parent / "fonts" / "InterVariable.ttf"
# Loaded fonts by (size, bold), so the font file is read once per size.
LOADED_FONTS = {}


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


def shorten_word(draw, word, font, max_width):
    """Return word cut with "…" so it fits max_width (for very long words)."""
    while len(word) > 1 and draw.textlength(f"{word}…", font=font) > max_width:
        word = word[:-1]
    return f"{word}…"


def wrap_text(draw, text, font, max_width):
    """Split text into lines that each fit within max_width pixels.

    A single word wider than a whole line (a long web address) is shortened
    with "…", so no text ever runs off the image.
    """
    lines = []
    current = ""
    for word in text.split():
        if draw.textlength(word, font=font) > max_width:
            word = shorten_word(draw, word, font, max_width)
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


def font_of(size, bold=False):
    """Return Inter at size pixels, in its Bold or Regular weight."""
    key = (size, bold)
    if key not in LOADED_FONTS:
        font = ImageFont.truetype(FONT_FILE, size)
        font.set_variation_by_name("Bold" if bold else "Regular")
        LOADED_FONTS[key] = font
    return LOADED_FONTS[key]


def fit_text(draw, text, max_width, fonts, room):
    """Return (font, lines) for the biggest font whose wrapped text fits.

    fonts are biggest first; room is (max_lines, max_height). If even the
    smallest font is too big, it is used and the text ends with "…" after
    as many lines as fit.
    """
    max_lines, max_height = room
    for font in fonts:
        lines = wrap_text(draw, text, font, max_width)
        height = len(lines) * line_height(font)
        if len(lines) <= max_lines and height <= max_height:
            return font, lines
    font = fonts[-1]
    lines = wrap_text(draw, text, font, max_width)
    fitting = max(1, min(max_lines, max_height // line_height(font)))
    return font, fit_lines(draw, lines, font, max_width, fitting)


def line_height(font):
    """Return the distance from one line of text to the next."""
    return int(font.size) * 6 // 5
