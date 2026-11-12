"""Tests for creating, listing and deleting content plans."""

import pytest
from django.contrib.auth import get_user_model

from planning.models import ContentPlan
from social.models import SocialAccount

URL = "/api/v1/plans/"


def make_user(email):
    """Create and return a saved user."""
    return get_user_model().objects.create_user(
        email=email, password="correct-horse-battery-staple"
    )


def make_account(user):
    """Link and return a demo social account for user."""
    return SocialAccount.objects.create(
        user=user, platform="demo", display_name="Demo", external_id=str(user.id)
    )


@pytest.fixture
def user(db):
    """The logged-in user in these tests."""
    return make_user("ada@example.com")


@pytest.fixture
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client


def plan_details(account, topic_count=1):
    """Return valid details for a new plan posting to account."""
    topics = []
    for number in range(topic_count):
        topics.append({"name": f"Topic {number}", "preset": "ai_news"})
    return {
        "name": "Tech news",
        "requirements": "Short, friendly posts for developers.",
        "topics": topics,
        "account_ids": [str(account.id)],
    }


def test_plans_need_a_login(api_client, db):
    assert api_client.get(URL).status_code == 401


def test_a_plan_is_created_with_its_topics_and_accounts(client, user):
    account = make_account(user)

    response = client.post(URL, plan_details(account, 2), format="json")

    assert response.status_code == 201
    body = response.json()
    assert [topic["preset"] for topic in body["topics"]] == ["ai_news", "ai_news"]
    assert body["accounts"][0]["id"] == str(account.id)
    assert body["approval_mode"] == "manual"
    assert body["ai_label_enabled"] is True


def test_a_plan_needs_a_topic_and_an_account(client):
    response = client.post(URL, {"name": "Empty"}, format="json")

    assert response.status_code == 400
    assert "topics" in response.json()["errors"]
    assert "account_ids" in response.json()["errors"]


def test_an_unknown_preset_is_refused(client, user):
    details = plan_details(make_account(user))
    details["topics"] = [{"name": "Space", "preset": "space_news"}]

    response = client.post(URL, details, format="json")

    assert response.status_code == 400


def test_another_users_account_cannot_be_used(client):
    theirs = make_account(make_user("grace@example.com"))

    response = client.post(URL, plan_details(theirs), format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_plan"
    assert not ContentPlan.objects.exists()


def test_a_plan_cannot_have_more_topics_than_the_limit(client, user):
    response = client.post(URL, plan_details(make_account(user), 7), format="json")

    assert response.status_code == 403
    assert response.json()["resource"] == "topics_per_plan"


def test_a_user_cannot_have_more_active_plans_than_the_limit(client, user):
    account = make_account(user)
    for _ in range(3):
        assert client.post(URL, plan_details(account), format="json").status_code == 201

    response = client.post(URL, plan_details(account), format="json")

    assert response.status_code == 403
    assert response.json()["resource"] == "active_plans"


def test_usage_shows_live_counts_of_plans_and_accounts(client, user):
    client.post(URL, plan_details(make_account(user)), format="json")

    limits = client.get("/api/v1/me/usage/").json()["limits"]
    used = {}
    for item in limits:
        used[item["resource"]] = item["used"]

    assert used["active_plans"] == 1
    assert used["social_accounts"] == 1


def test_users_only_see_and_delete_their_own_plans(client):
    other = make_user("grace@example.com")
    theirs = ContentPlan.objects.create(user=other, name="Grace's plan")

    assert client.get(URL).json() == []
    assert client.get(f"{URL}{theirs.id}/").status_code == 404
    assert client.delete(f"{URL}{theirs.id}/").status_code == 404
    assert ContentPlan.objects.filter(id=theirs.id).exists()


def test_a_user_can_delete_their_plan(client, user):
    plan_id = client.post(URL, plan_details(make_account(user)), format="json").json()[
        "id"
    ]

    assert client.delete(f"{URL}{plan_id}/").status_code == 204
    assert not ContentPlan.objects.exists()
