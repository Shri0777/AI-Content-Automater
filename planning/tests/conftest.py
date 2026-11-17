"""Shared setup for the planning tests: a user with a plan ready to schedule."""

import pytest
from django.contrib.auth import get_user_model

from credentials.services import save_credential
from planning.models import ContentPlan, Topic
from social.models import SocialAccount


@pytest.fixture
def user(db):
    """A user in Kolkata with demo text and image credentials."""
    user = get_user_model().objects.create_user(
        email="ada@example.com", password="correct-horse-battery-staple"
    )
    user.timezone = "Asia/Kolkata"
    user.save()
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    return user


@pytest.fixture
def plan(user):
    """A plan with one topic that posts to one demo account (no schedule yet)."""
    plan = ContentPlan.objects.create(user=user, name="Tech news")
    account = SocialAccount.objects.create(
        user=user, platform="demo", display_name="Demo account 1", external_id="d1"
    )
    plan.accounts.add(account)
    Topic.objects.create(plan=plan, name="Linux tips", preset="linux_tips")
    return plan


@pytest.fixture
def client(api_client, user):
    """An API client logged in as the user."""
    api_client.force_authenticate(user)
    return api_client
