"""Captions fit each platform: whole where they fit, rebuilt from their parts
(not cut mid-sentence) where the limit is short."""

from types import SimpleNamespace

from publishing.captions import fitted_caption, last_question

LINK = "https://example.com/a"
CAPTION = (
    "Why this matters to anyone paying for an API.\n\n" + "A long paragraph. " * 30
)
CAPTION = CAPTION + "\n\nWould a 50% price cut change which model you use?\n\n#AI"


def version(caption=CAPTION, takeaway="Long prompts cost half as much."):
    """Return a version with the words the caption is built from."""
    return SimpleNamespace(
        headline="Contoso halves its API price",
        takeaway=takeaway,
        points=["Input tokens now cost $1.25 per million."],
        caption=caption,
    )


def test_a_caption_that_fits_is_sent_whole():
    assert fitted_caption(version(caption="Short."), LINK, 3000) == "Short."


def test_a_short_limit_gets_the_headline_takeaway_question_and_link():
    text = fitted_caption(version(), LINK, 280)

    assert text == (
        "Contoso halves its API price\n\n"
        "Long prompts cost half as much.\n\n"
        "Would a 50% price cut change which model you use?\n\n"
        f"{LINK}"
    )


def test_the_least_important_part_is_left_out_first():
    text = fitted_caption(version(), LINK, 130)

    assert "Long prompts" not in text
    assert text.startswith("Contoso halves its API price")
    assert text.endswith(LINK)


def test_the_first_point_stands_in_for_a_missing_takeaway():
    text = fitted_caption(version(takeaway=""), LINK, 280)

    assert "Input tokens now cost $1.25 per million." in text


def test_the_last_question_is_found():
    assert last_question(CAPTION) == (
        "Would a 50% price cut change which model you use?"
    )
    assert last_question("No question here.") == ""


def test_when_nothing_fits_the_caption_is_left_for_cutting():
    assert fitted_caption(version(), LINK, 20) == CAPTION
