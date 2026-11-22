"""The parts every slide is drawn with: a frame, rows of text and a footer.

studio/slides.py uses these to lay out each kind of slide. Sizes are
designed for a 1080-pixel slide and scaled to the real size, so any width
and height work: the portrait slides and the square share image alike.
"""

from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from studio.palette import Palette
from studio.posters import fit_lines, fit_text, font_of, line_height, wrap_text

# Slides are designed for a 1080-pixel side; other sizes scale from it.
DESIGN_SIDE = 1080


@dataclass
class Deck:
    """Everything written on a post's slides, and how they look."""

    headline: str
    palette: Palette
    source_name: str = ""
    # A small line above the headline on the cover: the topic's name.
    kicker: str = ""
    points: list = field(default_factory=list)
    figure: dict = field(default_factory=dict)
    quote: dict = field(default_factory=dict)
    takeaway: str = ""
    # The AI artwork for the cover, as image bytes; empty for plain type.
    artwork: bytes = b""


@dataclass
class Frame:
    """One slide being drawn: its image, its colours and its text area."""

    image: Image.Image
    draw: ImageDraw.ImageDraw
    palette: Palette
    margin: int
    # Where the text area starts (lower on a cover with artwork).
    top: int


@dataclass
class TextStyle:
    """How a piece of text looks: design sizes (biggest first), colour, weight."""

    sizes: list
    colour: tuple
    bold: bool = False


@dataclass
class Row:
    """Some lines of text drawn in one font and colour."""

    lines: list
    font: object
    colour: tuple
    # Space left empty below the row.
    gap: int = 0


def new_frame(palette, width, height):
    """Return an empty slide of width x height in the background colour."""
    image = Image.new("RGB", (width, height), palette.background)
    margin = min(width, height) // 12
    return Frame(image, ImageDraw.Draw(image), palette, margin, margin)


def scaled(frame, size):
    """Return a size designed for a 1080-pixel slide, scaled to this one."""
    side = min(frame.image.width, frame.image.height)
    return max(12, size * side // DESIGN_SIDE)


def scaled_sizes(frame, sizes):
    """Return a list of design sizes scaled to this slide."""
    result = []
    for size in sizes:
        result.append(scaled(frame, size))
    return result


def text_width(frame):
    """Return how wide a line of text may be."""
    return frame.image.width - 2 * frame.margin


def footer_font(frame):
    """Return the small font of the footer (source and slide number)."""
    return font_of(scaled(frame, 30))


def text_bottom(frame):
    """Return the lowest y the slide's text may reach, above the footer."""
    footer = line_height(footer_font(frame))
    return frame.image.height - frame.margin - footer - frame.margin // 2


def rows_height(rows):
    """Return the height the rows need, gaps included."""
    total = 0
    for row in rows:
        total = total + len(row.lines) * line_height(row.font) + row.gap
    return total


def room_left(frame, rows):
    """Return the height still free in the text area below rows."""
    return text_bottom(frame) - frame.top - rows_height(rows)


def draw_rows(frame, rows, top):
    """Draw rows from top, at the left margin; return the y below them."""
    y = top
    for row in rows:
        for line in row.lines:
            frame.draw.text((frame.margin, y), line, font=row.font, fill=row.colour)
            y = y + line_height(row.font)
        y = y + row.gap
    return y


def draw_centred(frame, rows, extra_height=0):
    """Draw rows in the middle of the text area; return the y below them.

    extra_height keeps room below the rows for something else (the bars).
    """
    room = text_bottom(frame) - frame.top
    block = rows_height(rows) + extra_height
    top = frame.top + max(0, (room - block) // 2)
    return draw_rows(frame, rows, top)


def draw_footer(frame, left, right):
    """Draw the source on the left and the slide number on the right."""
    font = footer_font(frame)
    y = frame.image.height - frame.margin - line_height(font)
    right_width = frame.draw.textlength(right, font=font)
    room = text_width(frame) - int(right_width) - frame.margin // 2
    muted = frame.palette.muted
    if left and room > 0:
        lines = wrap_text(frame.draw, left, font, room)
        lines = fit_lines(frame.draw, lines, font, room, 1)
        frame.draw.text((frame.margin, y), lines[0], font=font, fill=muted)
    x = frame.image.width - frame.margin - right_width
    frame.draw.text((x, y), right, font=font, fill=muted)


def make_row(frame, text, style, room):
    """Return a Row of text in the biggest size of style that fits room.

    room is (max_lines, max_height).
    """
    max_lines, max_height = room
    fonts = []
    for size in scaled_sizes(frame, style.sizes):
        fonts.append(font_of(size, style.bold))
    room = (max_lines, max(1, max_height))
    font, lines = fit_text(frame.draw, text, text_width(frame), fonts, room)
    return Row(lines, font, style.colour)
