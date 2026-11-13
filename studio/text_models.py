"""The base class for a text model (the AI that writes and checks posts).

This is the adapter pattern. Each provider is one subclass that only knows
how to send messages and get text back: its ask() method. Everything else
is shared and lives here: building prompts (studio/prompts.py), reading the
JSON answer, checking it (studio/model_outputs.py) and asking once more if
it does not fit.

Providers: openai_compatible.py, anthropic_text.py and demo/text_model.py.
studio.providers.get_text_model() picks the right one for a credential.
"""

import json

from core.errors import ProviderError, ProviderKeyRejected
from studio.model_outputs import DraftOutput, ImagePromptOutput, ReviewOutput
from studio.prompts import (
    DRAFT_PROMPT,
    IMAGE_PROMPT_PROMPT,
    MAX_ARTICLE_CHARACTERS,
    REPAIR_MESSAGE,
    REVIEW_PROMPT,
)

MAX_HEADLINE_LENGTH = 90


def read_json_answer(answer, output_class):
    """Return (checked data, "") or (None, a description of the problem)."""
    start = answer.find("{")
    end = answer.rfind("}")
    if start == -1 or end < start:
        return None, "it did not contain a JSON object"
    try:
        data = json.loads(answer[start : end + 1])
    except ValueError:
        return None, "the JSON could not be read"
    checker = output_class(data=data)
    if not checker.is_valid():
        return None, f"some fields were wrong: {json.dumps(checker.errors)[:300]}"
    return checker.validated_data, ""


def article_values(article):
    """Return the article details the prompts fill in."""
    return {
        "title": article.title,
        "text": article.text[:MAX_ARTICLE_CHARACTERS],
        "source_name": article.source_name,
        "url": article.url,
    }


class TextModel:
    """The base class every text model follows."""

    def __init__(self, credential, api_key):
        self.credential = credential
        self.api_key = api_key
        # Added up over every request, then saved on the GenerationStep.
        self.input_tokens = 0
        self.output_tokens = 0
        self.prompt_versions = []

    def ask(self, system, messages):
        """Send a system prompt and messages; return the reply text.

        messages is a list of {"role": "user" or "assistant", "content": text}.
        Each provider adds the tokens it used to input_tokens and
        output_tokens.
        """
        raise NotImplementedError("Each text model must define ask().")

    def check_connection(self):
        """Make a small request that proves the key and model work."""
        raise NotImplementedError("Each text model must define check_connection().")

    def describe(self):
        """Return the provider and model, for example "anthropic:claude-opus-5-5"."""
        return f"{self.credential.adapter}:{self.credential.model_name}"

    def ask_safely(self, system, messages):
        """Call ask(), noting which credential a rejected key belongs to."""
        try:
            return self.ask(system, messages)
        except ProviderKeyRejected as error:
            error.credential = self.credential
            raise

    def ask_for_json(self, prompt, values, output_class):
        """Ask with one of the prompts and return its checked JSON answer."""
        self.prompt_versions.append(prompt["version"])
        messages = [{"role": "user", "content": prompt["user"].format_map(values)}]
        problem = ""
        for _ in range(2):
            answer = self.ask_safely(prompt["system"], messages)
            result, problem = read_json_answer(answer, output_class)
            if problem == "":
                return result
            messages = messages + [
                {"role": "assistant", "content": answer or "(empty answer)"},
                {"role": "user", "content": REPAIR_MESSAGE.format(problem=problem)},
            ]
        raise ProviderError(f"The text model did not give a usable answer: {problem}")

    def write_post(self, article, requirements):
        """Return {"headline": ..., "caption": ...}; the caption credits the source."""
        values = article_values(article)
        values["requirements"] = requirements or "(nothing specific)"
        result = self.ask_for_json(DRAFT_PROMPT, values, DraftOutput)
        caption = result["caption"]
        if article.url not in caption:
            caption = f"{caption}\n\nSource: {article.source_name}, {article.url}"
        return {
            "headline": result["headline"][:MAX_HEADLINE_LENGTH],
            "caption": caption,
        }

    def write_image_prompt(self, article, headline):
        """Return a prompt for the image model. It asks for no written words."""
        values = article_values(article)
        values["headline"] = headline
        result = self.ask_for_json(IMAGE_PROMPT_PROMPT, values, ImagePromptOutput)
        return result["prompt"]

    def review_post(self, article, headline, caption):
        """Return {"scores": {...}, "issues": [...]} for a written post."""
        values = article_values(article)
        values["headline"] = headline
        values["caption"] = caption
        result = self.ask_for_json(REVIEW_PROMPT, values, ReviewOutput)
        issues = []
        for issue in result["issues"]:
            issues.append(dict(issue))
        return {"scores": dict(result["scores"]), "issues": issues}
