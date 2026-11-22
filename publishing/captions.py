"""Fit a post's words to each platform's caption limit.

LinkedIn and Facebook take the whole caption. X takes only 280 characters,
and cutting the caption there would lose its question (which invites
replies, the signal X weighs most) and its source link. So for a short
limit the caption is rebuilt from its parts instead: the headline, the
takeaway, the question and the link, leaving out the least important part
until it fits.
"""


def last_question(caption):
    """Return the caption's last line that ends with "?", or ""."""
    for line in reversed(caption.splitlines()):
        line = line.strip()
        if line.endswith("?"):
            return line
    return ""


def joined(parts):
    """Return the non-empty parts, separated by blank lines."""
    return "\n\n".join([part for part in parts if part])


def short_caption(version, link, room):
    """Return the fullest short caption that fits room characters, or ""."""
    lead = version.takeaway
    if not lead and version.points:
        lead = version.points[0]
    question = last_question(version.caption)
    choices = [
        [version.headline, lead, question, link],
        [version.headline, question, link],
        [version.headline, lead, link],
        [version.headline, link],
    ]
    for parts in choices:
        text = joined(parts)
        if len(text) <= room:
            return text
    return ""


def fitted_caption(version, link, room):
    """Return the caption if it fits room, else a short one built to fit.

    If not even the headline and link fit, the whole caption is returned
    and the caller cuts it (publishing/services.py, add_ai_label).
    """
    if len(version.caption) <= room:
        return version.caption
    return short_caption(version, link, room) or version.caption
