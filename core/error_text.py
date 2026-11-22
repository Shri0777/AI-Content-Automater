"""Find the human sentence inside a service's error answer.

Most APIs answer an error with JSON such as
{"error": {"message": "The model ... does not exist", "type": "..."}}.
Users should read that sentence, not the whole JSON, so web.py shows the
sentence when there is one and the raw text otherwise.
"""

import json

MESSAGE_KEYS = ["error", "message", "detail"]


def readable_detail(content):
    """Return the error sentence in an answer's bytes, or the raw text."""
    text = content.decode(errors="replace")
    try:
        answer = json.loads(text)
    except ValueError:
        return text
    return message_in(answer) or text


def message_in(answer):
    """Return the first message found under the usual keys, or ""."""
    if not isinstance(answer, dict):
        return ""
    for key in MESSAGE_KEYS:
        value = answer.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("message"), str):
            return value["message"]
    return ""
