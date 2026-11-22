"""Read the writing rules from post_creation.md, at the top of the project.

The rules sit between the markers <!-- rules:start --> and
<!-- rules:end -->. They are read once when the app starts and placed in the
prompts that write and fix posts (studio/prompts.py), so the people who own
the product can change what posts look like by editing that file.

The prompt version includes a fingerprint of the rules, so every saved
GenerationStep shows which wording of the rules a post was written with.
"""

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

START_MARKER = "<!-- rules:start -->"
END_MARKER = "<!-- rules:end -->"


def rules_file():
    """Return the path of post_creation.md."""
    return Path(settings.BASE_DIR) / "post_creation.md"


def read_rules(path=None):
    """Return the text between the rules markers, or raise ImproperlyConfigured."""
    path = path or rules_file()
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        raise ImproperlyConfigured(f"Cannot read the post rules in {path}.") from None
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end < start:
        raise ImproperlyConfigured(
            f"{path} must hold the rules between {START_MARKER} and {END_MARKER}."
        )
    return text[start + len(START_MARKER) : end].strip()


def rules_version(rules):
    """Return a prompt version that changes whenever the rules change."""
    fingerprint = hashlib.sha256(rules.encode()).hexdigest()[:8]
    return f"draft-v3-{fingerprint}"
