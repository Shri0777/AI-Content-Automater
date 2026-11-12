"""Create, find and delete a user's content plans."""

from django.db import transaction

from core.errors import AppError
from planning.models import ContentPlan, Topic
from quotas.services import (
    check_count_allowed,
    check_total_limit,
    count_total_items,
)
from social.models import SocialAccount


class PlanNotFound(AppError):
    """Raised when a plan does not exist or belongs to someone else."""

    status = 404
    code = "not_found"
    title = "Not found"


class InvalidPlan(AppError):
    """Raised when a plan's details cannot work, such as an unknown account."""

    status = 400
    code = "invalid_plan"
    title = "Plan cannot be saved"


def get_plans(user):
    """Return the user's plans, oldest first."""
    return ContentPlan.objects.filter(user=user).prefetch_related("topics", "accounts")


def get_plan(user, plan_id):
    """Return one of the user's plans, or raise PlanNotFound."""
    plan = get_plans(user).filter(id=plan_id).first()
    if plan is None:
        raise PlanNotFound("That plan does not exist.")
    return plan


def find_accounts(user, account_ids):
    """Return the user's accounts with these ids, or raise InvalidPlan."""
    accounts = list(SocialAccount.objects.filter(user=user, id__in=account_ids))
    if len(accounts) != len(set(account_ids)):
        raise InvalidPlan("One of the chosen social accounts is not yours.")
    return accounts


def create_plan(user, details):
    """Create a plan with its topics and accounts, and return it.

    details holds name, requirements, approval_mode, ai_label_enabled,
    ai_label_text, topics (a list of {name, preset}) and account_ids.
    """
    active_count = count_total_items(user, "active_plans")
    check_total_limit(user, "active_plans", active_count)
    check_count_allowed(user, "topics_per_plan", len(details["topics"]))
    accounts = find_accounts(user, details["account_ids"])
    with transaction.atomic():
        plan = ContentPlan.objects.create(
            user=user,
            name=details["name"],
            requirements=details["requirements"],
            approval_mode=details["approval_mode"],
            ai_label_enabled=details["ai_label_enabled"],
            ai_label_text=details["ai_label_text"],
        )
        plan.accounts.set(accounts)
        for topic in details["topics"]:
            Topic.objects.create(plan=plan, name=topic["name"], preset=topic["preset"])
    return get_plan(user, plan.id)


def delete_plan(user, plan_id):
    """Delete one of the user's plans and everything made for it."""
    get_plan(user, plan_id).delete()
