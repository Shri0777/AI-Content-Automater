"""Shared setup for the studio tests: a user ready to make posts."""

import pytest
from django.contrib.auth import get_user_model

from credentials.services import save_credential
from planning.models import ContentPlan, Topic
from social.models import SocialAccount


@pytest.fixture
def user(db):
    """A user with demo text and image credentials saved."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    return user


@pytest.fixture
def account(user):
    """A linked demo social account."""
    return SocialAccount.objects.create(
        user=user, platform="demo", display_name="Demo account 1", external_id="d1"
    )


@pytest.fixture
def plan(user, account):
    """A plan with one AI news topic that posts to the demo account."""
    plan = ContentPlan.objects.create(user=user, name="Tech news")
    plan.accounts.set([account])
    Topic.objects.create(plan=plan, name="AI news", preset="ai_news")
    return plan


@pytest.fixture
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client
