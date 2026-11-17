"""No user can reach another user's data through any API address (IDOR).

The test walks EVERY /api/v1/ address that takes an id, tries every method
the view supports as a second user, with the first user's ids, and checks
that each attempt is refused (404 Not Found, or 405 for an unused method)
and that nothing of the first user's changed. A new address with an id this
test does not know makes it fail, so new endpoints cannot skip the check.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import get_resolver

from credentials.services import save_credential
from notifications.services import notify
from planning.models import ContentPlan, Topic
from publishing.models import Publication
from social.models import SocialAccount
from studio.models import Post
from studio.runner import run_stage

METHODS = ["get", "post", "put", "patch", "delete"]
REFUSED = [404, 405]
# Valid input for every endpoint at once (serializers ignore extra fields),
# so a refusal can only come from the ownership check, not from bad input.
VALID_BODY = {
    "schedule_rules": [],
    "caption": "Hijacked caption",
    "outcome": "published",
}


def api_routes_with_ids():
    """Return every /api/v1/ route pattern that contains a <uuid:...> part."""
    routes = []

    def walk(patterns, prefix):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                walk(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                route = prefix + str(pattern.pattern)
                if route.startswith("api/v1/") and "<uuid:" in route:
                    routes.append((route, pattern.callback.view_class))

    walk(get_resolver().url_patterns, "")
    return routes


def fill_in(route, ids):
    """Replace each <uuid:name> in route with the matching id."""
    address = "/" + route
    for name, value in ids.items():
        address = address.replace(f"<uuid:{name}>", str(value))
    assert "<" not in address, f"Add an owned object for this id: {route}"
    return address


def made_post(user, plan, topic):
    """Return a demo post run through every stage until it waits for approval."""
    post = Post.objects.create(user=user, plan=plan, topic=topic, demo_mode=True)
    for _ in range(6):
        run_stage(post.id)
    return post


@pytest.fixture
def owner_data(db):
    """One of everything a user can own, all belonging to Ada."""
    ada = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    credential = save_credential(ada, {"kind": "text", "adapter": "demo"})
    save_credential(ada, {"kind": "image", "adapter": "demo"})
    account = SocialAccount.objects.create(
        user=ada, platform="demo", display_name="Ada's", external_id="a1"
    )
    plan = ContentPlan.objects.create(user=ada, name="Ada's plan")
    plan.accounts.add(account)
    topic = Topic.objects.create(plan=plan, name="AI", preset="ai_news")
    post = made_post(ada, plan, topic)
    publication = Publication.objects.create(
        post=post,
        version=post.final_version(),
        account=account,
        idempotency_key="ada-1",
        status="ambiguous",
    )
    notification = notify(ada, "post_published", "Ada's post is live.")
    return {
        "notification_id": notification.id,
        "credential_id": credential.id,
        "account_id": account.id,
        "plan_id": plan.id,
        "post_id": post.id,
        "publication_id": publication.id,
    }


def test_every_address_refuses_another_users_ids(owner_data, api_client):
    stranger = get_user_model().objects.create_user(
        email="mallory@example.com", password="correct-horse-battery-staple"
    )
    api_client.force_authenticate(stranger)
    post_status = Post.objects.get(id=owner_data["post_id"]).status
    tried = 0

    for route, view_class in api_routes_with_ids():
        address = fill_in(route, owner_data)
        for method in METHODS:
            if not hasattr(view_class, method):
                continue
            response = getattr(api_client, method)(address, VALID_BODY, format="json")
            assert response.status_code in REFUSED, f"{method.upper()} {address}"
            tried = tried + 1

    assert tried >= 15
    assert ContentPlan.objects.get(id=owner_data["plan_id"]).paused is False
    assert Post.objects.get(id=owner_data["post_id"]).status == post_status
    assert SocialAccount.objects.filter(id=owner_data["account_id"]).exists()
    publication = Publication.objects.get(id=owner_data["publication_id"])
    assert publication.status == "ambiguous"
