"""Posts follow post_creation.md: a specific headline, key points, a deeper caption."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured

from studio.post_content import finished_post
from studio.post_rules import read_rules, rules_version
from studio.prompts import CORRECT_PROMPT, DRAFT_PROMPT, REVIEW_PROMPT

ARTICLE = SimpleNamespace(
    url="https://example.com/a",
    source_name="Example News",
    title="Folder sizes",
    text="Use du to list folder sizes.",
)


def generate(client, plan):
    """Ask for a post now and return its id."""
    return client.post(f"/api/v1/plans/{plan.id}/generate-now/").json()["id"]


def test_the_rules_the_ai_follows_come_from_post_creation_md():
    rules = read_rules()

    assert "Key points" in rules
    assert "rules:start" not in rules
    assert rules in DRAFT_PROMPT["system"]
    assert rules in CORRECT_PROMPT["system"]
    assert "{points}" in REVIEW_PROMPT["user"]


def test_the_prompt_version_changes_when_the_rules_change():
    first = rules_version("Write well.")
    second = rules_version("Write very well.")

    assert first != second
    assert first.startswith("draft-v3-")


def test_a_rules_file_without_its_markers_is_refused(tmp_path):
    rules_file = tmp_path / "post_creation.md"
    rules_file.write_text("# Notes\nNo markers here.")

    with pytest.raises(ImproperlyConfigured, match="rules:start"):
        read_rules(rules_file)


def test_filler_openers_are_removed_and_points_kept_to_five():
    result = {
        "headline": "Quick tip: List folder sizes with du",
        "points": ["One.", "Two.", "Three.", "Four.", "Five.", "Six."],
        "caption": "Why it matters.",
    }

    finished = finished_post(result, ARTICLE)

    assert finished["headline"] == "List folder sizes with du"
    assert finished["points"] == ["One.", "Two.", "Three.", "Four.", "Five."]
    assert finished["caption"].endswith("Source: Example News, https://example.com/a")


def test_a_new_post_has_key_points(client, plan):
    post_id = generate(client, plan)

    version = client.get(f"/api/v1/posts/{post_id}/").json()["versions"][0]

    # The rules allow fewer points when the article is thin.
    assert 2 <= len(version["points"]) <= 5
    assert all(point.strip() for point in version["points"])


def test_the_user_can_rewrite_the_key_points(client, plan):
    post_id = generate(client, plan)
    body = {"caption": "My caption.", "points": ["First fact.", "Second fact."]}

    response = client.patch(f"/api/v1/posts/{post_id}/", body, format="json")

    edited = response.json()["versions"][-1]
    assert response.status_code == 200
    assert edited["points"] == ["First fact.", "Second fact."]
