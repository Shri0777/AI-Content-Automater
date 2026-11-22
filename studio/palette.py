"""Choose readable slide colours from a plan's brand colour.

The owner picks one background colour. Every other colour on a slide is
chosen from it so that text always passes WCAG AA contrast (4.5 : 1), on any
background: either white or black text always reaches at least 4.58 : 1.

Contrast is worked out with the WCAG formula for relative luminance:
https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
"""

from dataclasses import dataclass

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# WCAG AA for normal-size text.
MIN_CONTRAST = 4.5
# Accent colours to try, in order of preference: the first one readable on
# the background is used for numbers, labels and bars.
ACCENT_CHOICES = [
    (255, 196, 0),
    (92, 225, 230),
    (255, 138, 101),
    (0, 82, 204),
    (176, 0, 92),
    (0, 102, 68),
]


@dataclass
class Palette:
    """The colours of every slide of one post."""

    background: tuple
    text: tuple
    muted: tuple
    accent: tuple


def hex_to_rgb(colour):
    """Return "#RRGGBB" as an (r, g, b) tuple."""
    colour = colour.lstrip("#")
    return (int(colour[0:2], 16), int(colour[2:4], 16), int(colour[4:6], 16))


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


def contrast_ratio(first, second):
    """Return the WCAG contrast ratio of two colours (1 to 21)."""
    lighter = relative_luminance(first) + 0.05
    darker = relative_luminance(second) + 0.05
    if darker > lighter:
        lighter, darker = darker, lighter
    return lighter / darker


def blend(first, second, share):
    """Return the colour share of the way from first to second."""
    mixed = []
    for index in range(3):
        mixed.append(round(first[index] + (second[index] - first[index]) * share))
    return tuple(mixed)


def muted_text(text, background):
    """Return the softest blend of text into background that stays readable."""
    for share in [0.35, 0.3, 0.25, 0.2, 0.15, 0.1]:
        candidate = blend(text, background, share)
        if contrast_ratio(candidate, background) >= MIN_CONTRAST:
            return candidate
    return text


def accent_for(background, text):
    """Return the first accent colour readable on background, or the text colour."""
    for colour in ACCENT_CHOICES:
        if contrast_ratio(colour, background) >= MIN_CONTRAST:
            return colour
    return text


def palette_for(brand_colour):
    """Return the slide colours for a "#RRGGBB" brand colour."""
    background = hex_to_rgb(brand_colour)
    text = WHITE
    if contrast_ratio(BLACK, background) > contrast_ratio(WHITE, background):
        text = BLACK
    return Palette(
        background=background,
        text=text,
        muted=muted_text(text, background),
        accent=accent_for(background, text),
    )
