"""Lay out a post's slides (post_creation.md, "What a post is now").

render_slides() draws one portrait image per slide, in this order:

    cover -> figure (if any) -> one slide per key point -> quote (if any)
    -> closing (the takeaway and the source)

Each slide holds one idea in big type, so it can be read in two seconds.
render_share_image() draws the one image for platforms that show a single
picture: the figure slide when there is one, else the cover.
slides_to_pdf() joins the slides into the PDF of a LinkedIn document post.
The parts every slide is drawn with are in studio/slide_parts.py.
"""

from io import BytesIO

from PIL import Image

from studio.posters import font_of, line_height, open_artwork, to_png_bytes
from studio.slide_parts import (
    TextStyle,
    draw_centred,
    draw_footer,
    draw_rows,
    make_row,
    new_frame,
    room_left,
    scaled,
    text_width,
)

# Design sizes (for a 1080-pixel slide), biggest first.
HEADLINE_SIZES = [112, 100, 88, 78, 68, 60, 52]
BODY_SIZES = [64, 58, 52, 48, 44, 40]
FIGURE_SIZES = [300, 260, 220, 190, 160, 130, 110, 90, 72]
SMALL_SIZES = [34]
BAR_HEIGHT = 44
# Point slides start this far below the top, so swiping keeps text in place.
POINT_TOP = 150


def small_row(frame, text, colour, gap=24):
    """Return a Row of small text (at most 2 lines), such as a kicker."""
    style = TextStyle(SMALL_SIZES, colour)
    row = make_row(frame, text, style, (2, room_left(frame, [])))
    row.gap = scaled(frame, gap)
    return row


def draw_cover(frame, deck, number):
    """Draw the cover: the topic and the headline, with artwork if any."""
    if deck.artwork:
        band = frame.image.height * 2 // 5
        artwork = open_artwork(deck.artwork, frame.image.width, band)
        frame.image.paste(artwork.convert("RGB"), (0, 0))
        frame.top = band + frame.margin // 2
    rows = []
    if deck.kicker:
        rows.append(small_row(frame, deck.kicker.upper(), frame.palette.accent))
    style = TextStyle(HEADLINE_SIZES, frame.palette.text, bold=True)
    rows.append(make_row(frame, deck.headline, style, (6, room_left(frame, rows))))
    draw_centred(frame, rows)


def bars_height(frame, bars):
    """Return the height the comparison bars need (0 without bars)."""
    each = line_height(font_of(scaled(frame, 36))) + scaled(frame, BAR_HEIGHT + 28)
    return each * len(bars)


def draw_bars(frame, bars, top):
    """Draw two labelled bars, their lengths in proportion to their amounts."""
    font = font_of(scaled(frame, 36))
    largest = 0
    for bar in bars:
        largest = max(largest, bar["amount"])
    # The first bar ("before") is quiet, the second ("after") stands out.
    colours = [frame.palette.muted, frame.palette.accent]
    text = frame.palette.text
    y = top
    for index, bar in enumerate(bars):
        frame.draw.text((frame.margin, y), bar["label"], font=font, fill=text)
        display_width = frame.draw.textlength(bar["display"], font=font)
        display_x = frame.margin + text_width(frame) - display_width
        frame.draw.text((display_x, y), bar["display"], font=font, fill=text)
        y = y + line_height(font)
        share = bar["amount"] / largest if largest else 0
        length = max(scaled(frame, 12), int(text_width(frame) * share))
        box = [frame.margin, y, frame.margin + length, y + scaled(frame, BAR_HEIGHT)]
        frame.draw.rectangle(box, fill=colours[index % 2])
        y = y + scaled(frame, BAR_HEIGHT + 28)


def draw_figure(frame, deck, number):
    """Draw the figure: its number big, what it means, and bars if any."""
    figure = deck.figure
    palette = frame.palette
    bars = figure.get("compare") or []
    rows = [small_row(frame, deck.headline, palette.muted, gap=32)]
    room = (1, room_left(frame, rows) - bars_height(frame, bars))
    style = TextStyle(FIGURE_SIZES, palette.accent, bold=True)
    rows.append(make_row(frame, figure["value"], style, room))
    room = (4, room_left(frame, rows) - bars_height(frame, bars))
    label = make_row(frame, figure["label"], TextStyle(BODY_SIZES, palette.text), room)
    label.gap = scaled(frame, 40)
    rows.append(label)
    bottom = draw_centred(frame, rows, bars_height(frame, bars))
    if bars:
        draw_bars(frame, bars, bottom)


def draw_point(frame, deck, number):
    """Draw one key point, with its number and the headline above it."""
    palette = frame.palette
    frame.top = frame.margin + scaled(frame, POINT_TOP)
    rows = [small_row(frame, deck.headline, palette.muted, gap=16)]
    numeral = TextStyle([150], palette.accent, bold=True)
    rows.append(make_row(frame, f"{number}", numeral, (1, room_left(frame, rows))))
    style = TextStyle(BODY_SIZES, palette.text)
    point = deck.points[number - 1]
    rows.append(make_row(frame, point, style, (9, room_left(frame, rows))))
    draw_rows(frame, rows, frame.top)


def draw_quote(frame, deck, number):
    """Draw the quote, word for word, with who said it."""
    palette = frame.palette
    mark_style = TextStyle([200], palette.accent, bold=True)
    mark = make_row(frame, "\u201c", mark_style, (1, room_left(frame, [])))
    speaker = deck.quote.get("speaker") or deck.source_name
    by = small_row(frame, f"\u2014 {speaker}", palette.muted)
    room = (9, room_left(frame, [mark, by]) - scaled(frame, 40))
    words = make_row(
        frame, deck.quote["text"], TextStyle(BODY_SIZES, palette.text), room
    )
    words.gap = scaled(frame, 40)
    draw_centred(frame, [mark, words, by])


def draw_closing(frame, deck, number):
    """Draw the closing slide: why it matters, then where the story is from."""
    palette = frame.palette
    label = "WHY IT MATTERS"
    message = deck.takeaway
    if not message:
        label = "IN SHORT"
        message = deck.headline
    rows = [small_row(frame, label, palette.accent)]
    source = small_row(frame, f"Full story: {deck.source_name}", palette.muted)
    room = (6, room_left(frame, rows + [source]) - scaled(frame, 48))
    style = TextStyle(BODY_SIZES, palette.text, bold=True)
    takeaway = make_row(frame, message, style, room)
    takeaway.gap = scaled(frame, 48)
    draw_centred(frame, rows + [takeaway, source])


# How each kind of slide is drawn: function(frame, deck, point number).
LAYOUTS = {
    "cover": draw_cover,
    "figure": draw_figure,
    "point": draw_point,
    "quote": draw_quote,
    "closing": draw_closing,
}


def slide_plan(deck):
    """Return the slides to draw, in order, as (kind, point number) pairs."""
    plan = [("cover", 0)]
    if deck.figure:
        plan.append(("figure", 0))
    for number in range(1, len(deck.points) + 1):
        plan.append(("point", number))
    if deck.quote:
        plan.append(("quote", 0))
    plan.append(("closing", 0))
    return plan


def draw_slide(deck, kind, number, size):
    """Return the Frame of one slide of the given kind, drawn at size."""
    frame = new_frame(deck.palette, size[0], size[1])
    LAYOUTS[kind](frame, deck, number)
    return frame


def render_slides(deck, width, height):
    """Return every slide as PNG bytes, in order, numbered "2/7" and so on."""
    plan = slide_plan(deck)
    images = []
    for position, (kind, number) in enumerate(plan, start=1):
        frame = draw_slide(deck, kind, number, (width, height))
        draw_footer(frame, deck.source_name, f"{position}/{len(plan)}")
        images.append(to_png_bytes(frame.image))
    return images


def render_share_image(deck, width, height):
    """Return PNG bytes of the one image for single-picture platforms."""
    kind = "cover"
    if deck.figure:
        kind = "figure"
    frame = draw_slide(deck, kind, 0, (width, height))
    draw_footer(frame, deck.source_name, "")
    return to_png_bytes(frame.image)


def slides_to_pdf(slide_pngs):
    """Return one PDF with a page per slide, for LinkedIn's document posts."""
    pages = []
    for png in slide_pngs:
        pages.append(Image.open(BytesIO(png)).convert("RGB"))
    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:])
    return output.getvalue()
