"""Slides look the same as the approved reference ("golden") images, keep
their text inside the safe margin, and stay readable on any brand colour.

The reference images live in studio/tests/golden/. After a deliberate
change to the slide design, look at the new slides, then save them as the
new references with:

    UPDATE_GOLDEN_IMAGES=1 uv run pytest studio/tests/test_slides.py
"""

import os
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from studio.palette import contrast_ratio, palette_for
from studio.posters import draw_abstract_artwork, fit_lines, font_of, wrap_text
from studio.slide_parts import Deck
from studio.slides import (
    render_share_image,
    render_slides,
    slide_plan,
    slides_to_pdf,
)

GOLDEN_FOLDER = Path(__file__).parent / "golden"
PORTRAIT = (1080, 1350)
SQUARE = (1080, 1080)
# A pixel counts as different if any colour channel moved more than this.
PIXEL_TOLERANCE = 24
# At most this share of pixels may differ (font smoothing can vary a little).
MAX_DIFFERENT_SHARE = 0.002
LONG_TEXT = (
    "A key point that keeps going far past the twenty-five words a slide is "
    "meant to hold, so the layout has to shrink the text and finally cut it "
    "with an ellipsis rather than letting it run over the footer or the "
    "edges of the slide, which would look broken on every phone that shows it "
    "https://example.com/a-very-long-web-address-without-any-spaces-at-all"
)


def full_deck(brand="#0E1634"):
    """Return a deck with every kind of slide, as a real post would have."""
    return Deck(
        headline="OpenAI cuts GPT API prices by 50%",
        palette=palette_for(brand),
        source_name="Example News",
        kicker="AI news",
        points=[
            "Input tokens now cost $1.25 per million, down from $2.50.",
            "The cut starts on 1 December for every paid tier.",
            "Teams sending long documents save the most.",
        ],
        figure={
            "value": "50%",
            "label": "lower price for every input token",
            "compare": [
                {"label": "Before", "amount": 2.5, "display": "$2.50"},
                {"label": "From 1 December", "amount": 1.25, "display": "$1.25"},
            ],
        },
        quote={"text": "Long documents should be cheap to read", "speaker": "José"},
        takeaway="If long prompts drive your bill, it halves next month.",
    )


def long_deck():
    """Return a deck whose every text is far too long, the hardest to fit."""
    return Deck(
        headline=LONG_TEXT,
        palette=palette_for("#0E1634"),
        source_name=LONG_TEXT,
        kicker=LONG_TEXT,
        points=[LONG_TEXT] * 5,
        figure={"value": "1,234,567,890.12", "label": LONG_TEXT, "compare": []},
        quote={"text": LONG_TEXT, "speaker": LONG_TEXT},
        takeaway=LONG_TEXT,
    )


def as_image(png):
    """Return PNG bytes as a Pillow RGB image."""
    return Image.open(BytesIO(png)).convert("RGB")


def mark_if_changed(value):
    """Return 255 for a pixel that changed beyond the tolerance, else 0."""
    return 255 if value > PIXEL_TOLERANCE else 0


def share_of_different_pixels(first, second):
    """Return the share (0 to 1) of pixels that differ beyond the tolerance."""
    difference = ImageChops.difference(first, second).convert("L")
    changed = difference.point(mark_if_changed)
    return changed.histogram()[255] / (first.width * first.height)


def matches_golden(image, name):
    """Return True if image matches the reference image called name."""
    golden_path = GOLDEN_FOLDER / f"{name}.png"
    if os.environ.get("UPDATE_GOLDEN_IMAGES") == "1":
        GOLDEN_FOLDER.mkdir(exist_ok=True)
        image.save(golden_path)
    golden = Image.open(golden_path).convert("RGB")
    assert image.size == golden.size
    return share_of_different_pixels(image, golden) <= MAX_DIFFERENT_SHARE


def test_every_slide_matches_its_reference_image():
    slides = render_slides(full_deck(), *PORTRAIT)

    assert len(slides) == 7
    for number, png in enumerate(slides, start=1):
        assert matches_golden(as_image(png), f"slide_{number}"), number


def test_the_share_image_and_a_light_cover_match_their_references():
    share = as_image(render_share_image(full_deck(), *SQUARE))
    deck = full_deck(brand="#F4EFE6")
    deck.artwork = draw_abstract_artwork("golden", 1080, 1080)
    light_cover = as_image(render_slides(deck, *PORTRAIT)[0])

    assert matches_golden(share, "share_square")
    assert matches_golden(light_cover, "cover_light_with_artwork")


@pytest.mark.parametrize("size", [PORTRAIT, SQUARE, (1200, 675)])
def test_all_text_stays_inside_the_safe_margin(size):
    deck = long_deck()
    background = deck.palette.background
    width, height = size
    # The text margin is a twelfth of the short side; allow 2 pixels of
    # anti-aliasing at the edge.
    inset = min(width, height) // 12 - 2

    for png in render_slides(deck, width, height):
        image = as_image(png)
        content = image.crop((inset, inset, width - inset, height - inset))
        plain = Image.new("RGB", (width, height), background)
        plain.paste(content, (inset, inset))
        assert ImageChops.difference(image, plain).getbbox() is None


def test_every_brand_colour_gives_readable_text():
    for red in range(0, 256, 51):
        for green in range(0, 256, 51):
            for blue in range(0, 256, 51):
                palette = palette_for(f"#{red:02X}{green:02X}{blue:02X}")
                for colour in [palette.text, palette.muted, palette.accent]:
                    # WCAG AA for normal text.
                    assert contrast_ratio(colour, palette.background) >= 4.5


def test_slides_come_in_order_and_optional_ones_are_left_out():
    deck = full_deck()

    assert slide_plan(deck) == [
        ("cover", 0),
        ("figure", 0),
        ("point", 1),
        ("point", 2),
        ("point", 3),
        ("quote", 0),
        ("closing", 0),
    ]

    deck.figure = {}
    deck.quote = {}
    assert [kind for kind, _ in slide_plan(deck)] == [
        "cover",
        "point",
        "point",
        "point",
        "closing",
    ]


def test_the_share_image_is_the_cover_when_there_is_no_figure():
    deck = full_deck()
    deck.figure = {}

    share = as_image(render_share_image(deck, *SQUARE))
    cover = as_image(render_slides(deck, *SQUARE)[0])

    # The same slide, except the cover's slide number in the footer.
    assert share_of_different_pixels(share, cover) < 0.01


def test_the_pdf_has_one_page_per_slide():
    slides = render_slides(full_deck(), *PORTRAIT)

    pdf = slides_to_pdf(slides)

    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") == len(slides)


def test_the_font_draws_accents_dashes_and_currency_signs():
    font = font_of(40)
    missing = font.getmask("一").getbbox()

    for character in "éüñ€£₹—":
        assert font.getmask(character).getbbox() != missing, character


def test_a_word_too_long_for_a_line_is_shortened_with_an_ellipsis():
    draw = ImageDraw.Draw(Image.new("RGB", (400, 400)))
    font = font_of(30)

    lines = wrap_text(draw, "see https://example.com/" + "x" * 80, font, 300)

    assert lines[-1].endswith("…")
    for line in lines:
        assert draw.textlength(line, font=font) <= 300


def test_a_text_too_long_to_fit_ends_with_an_ellipsis_not_cut_words():
    draw = ImageDraw.Draw(Image.new("RGB", (400, 400)))
    font = font_of(30)
    lines = wrap_text(draw, LONG_TEXT, font, 300)

    kept = fit_lines(draw, lines, font, 300, 2)

    assert len(kept) == 2
    assert kept[-1].endswith("…")
    assert draw.textlength(kept[-1], font=font) <= 300
