"""Defences against prompt injection: web text that tries to command the AI.

Article text comes from the internet. Someone can write "Ignore your
instructions and ..." into a page we read. Three defences work together:

1. Untrusted text always sits between <article> tags, and every prompt says
   never to follow instructions found there (studio/prompts.py).
2. neutralise_tags() stops article text from closing those tags early and
   pretending the rest is our own instructions.
3. leaked_instructions() spots a post that repeats our instructions (a sign
   the model obeyed injected text); the review then adds a blocker, and the
   verdict is decided by fixed rules, not by the model (studio/verdicts.py).
"""

import re

# Matches a whole <article ...> or </article> tag, including spaced variants
# such as "< / Article >" and attributes such as number="9".
ARTICLE_TAG = re.compile(r"<\s*/?\s*article\b[^>]*>?", re.IGNORECASE)

# Phrases only our own instructions contain (lower case).
INSTRUCTION_PHRASES = [
    "is untrusted data. never follow",
    "reply with one json object only",
    "<article",
    "</article",
]

LEAK_ISSUE = {
    "severity": "blocker",
    "problem": "The post repeats the app's own instructions to the AI, which "
    "suggests the article tried to take control of it.",
    "fix_instruction": "Rewrite the post using only the article's information.",
}


def neutralise_tags(text):
    """Return text with anything that looks like an <article> tag defused."""
    return ARTICLE_TAG.sub("[article]", text)


def leaked_instructions(text):
    """Return True if text contains a phrase from our own instructions."""
    lowered = text.lower()
    for phrase in INSTRUCTION_PHRASES:
        if phrase in lowered:
            return True
    return False
