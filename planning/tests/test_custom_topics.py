"""The topic catalogue, and topics users write themselves.

A custom topic has the user's own name, the words to look for in the news
and the user's own instructions for the AI.
"""

import pytest

from demo.text_model import DemoTextModel
from newsroom.presets import TOPIC_CATEGORIES, TOPIC_PRESETS, get_preset
from planning.models import Topic
from social.models import SocialAccount

PLANS_URL = "/api/v1/plans/"
CUSTOM = {
    "name": "Indian EV market",
    "preset": "custom",
    "search_words": "electric vehicle, EV, battery, India",
    "instructions": "Focus on prices in rupees and what changes for buyers.",
}


@pytest.fixture
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def account(user):
    """A demo account to post to."""
    return SocialAccount.objects.create(
        user=user, platform="demo", display_name="Demo account 1", external_id="d1"
    )


def new_plan(client, account, topics):
    """Create a plan with topics and return the response."""
    body = {"name": "My plan", "topics": topics, "account_ids": [str(account.id)]}
    return client.post(PLANS_URL, body, format="json")


def test_every_topic_in_the_catalogue_is_complete():
    assert len(TOPIC_PRESETS) >= 30
    for key, preset in TOPIC_PRESETS.items():
        assert preset["category"] in TOPIC_CATEGORIES, key
        assert preset["label"] and preset["description"], key
        assert preset["sources"] and preset["keywords"], key


def test_the_topic_list_endpoint_groups_topics_for_the_picker(client):
    body = client.get("/api/v1/news/topics/").json()

    assert body["categories"] == TOPIC_CATEGORIES
    keys = [topic["key"] for topic in body["topics"]]
    assert set(keys) == set(TOPIC_PRESETS)
    assert set(body["topics"][0]) == {"key", "label", "category", "description"}


def test_a_plan_can_have_a_custom_topic(client, account):
    response = new_plan(client, account, [CUSTOM])

    assert response.status_code == 201, response.json()
    topic = Topic.objects.get(name="Indian EV market")
    assert topic.preset == f"custom-{topic.id.hex}"
    assert topic.instructions == CUSTOM["instructions"]
    shown = response.json()["topics"][0]
    assert shown["search_words"] == CUSTOM["search_words"]


def test_a_custom_topic_needs_words_to_search_for(client, account):
    response = new_plan(client, account, [{**CUSTOM, "search_words": " , "}])

    assert response.status_code == 400
    assert "search_words" in str(response.json())


def test_an_unknown_preset_is_refused(client, account):
    response = new_plan(client, account, [{"name": "X", "preset": "no-such-topic"}])

    assert response.status_code == 400


def test_a_custom_topic_reads_news_that_mentions_its_words(client, account):
    new_plan(client, account, [CUSTOM])
    topic = Topic.objects.get(name="Indian EV market")

    preset = get_preset(topic.preset)

    assert preset["label"] == "Indian EV market"
    assert preset["keywords"] == ["electric vehicle", "ev", "battery", "india"]
    search = [source for source in preset["sources"] if source["type"] == "hackernews"]
    assert search[0]["query"] == "electric vehicle EV battery India"
    broad = [source for source in preset["sources"] if source["type"] == "rss"]
    assert broad and all(source["broad"] for source in broad)


def test_the_ai_follows_a_custom_topics_instructions(client, account, monkeypatch):
    seen = []

    def remember_requirements(self, article, requirements):
        seen.append(requirements)
        return {"headline": "H", "points": ["A fact."], "caption": f"C {article.url}"}

    monkeypatch.setattr(DemoTextModel, "write_post", remember_requirements)
    plan_id = new_plan(client, account, [CUSTOM]).json()["id"]

    client.post(f"{PLANS_URL}{plan_id}/generate-now/")

    assert seen and CUSTOM["instructions"] in seen[0]
