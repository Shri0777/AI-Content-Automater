"""Create, find, schedule, pause and delete a user's content plans."""

from django.db import transaction
from django.utils import timezone

from core.errors import AppError
from planning.models import ContentPlan, PostSlot, ScheduleRule, Topic
from planning.schedule import make_slots, remove_future_slots
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
    return ContentPlan.objects.filter(user=user).prefetch_related(
        "topics", "accounts", "schedule_rules"
    )


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


def most_posts_on_one_weekday(rules):
    """Return the largest number of posting times any single weekday has."""
    most = 0
    for weekday in range(7):
        count = 0
        for rule in rules:
            if weekday in rule["days_of_week"]:
                count = count + len(rule["times"])
        most = max(most, count)
    return most


def save_rules(plan, rules):
    """Replace the plan's schedule rules with rules (a list of dicts)."""
    plan.schedule_rules.all().delete()
    for rule in rules:
        ScheduleRule.objects.create(
            plan=plan,
            days_of_week=sorted(set(rule["days_of_week"])),
            times=sorted(set(rule["times"])),
            timezone=rule.get("timezone") or plan.user.timezone,
        )


def save_new_plan(user, details):
    """Save the plan's own fields (not topics, accounts or schedule)."""
    return ContentPlan.objects.create(
        user=user,
        name=details["name"],
        requirements=details["requirements"],
        approval_mode=details["approval_mode"],
        ai_label_enabled=details["ai_label_enabled"],
        ai_label_text=details["ai_label_text"],
        lead_time_minutes=details["lead_time_minutes"],
        max_lateness_minutes=details["max_lateness_minutes"],
        on_missed_approval=details["on_missed_approval"],
    )


def create_plan(user, details):
    """Create a plan with its topics, accounts and schedule, and return it.

    details holds name, requirements, approval_mode, ai_label_enabled,
    ai_label_text, lead_time_minutes, max_lateness_minutes,
    on_missed_approval, topics (a list of {name, preset}), account_ids and
    schedule_rules (a list of {days_of_week, times, timezone}).
    """
    active_count = count_total_items(user, "active_plans")
    check_total_limit(user, "active_plans", active_count)
    check_count_allowed(user, "topics_per_plan", len(details["topics"]))
    rules = details.get("schedule_rules", [])
    check_count_allowed(
        user, "posts_per_plan_per_day", most_posts_on_one_weekday(rules)
    )
    accounts = find_accounts(user, details["account_ids"])
    with transaction.atomic():
        plan = save_new_plan(user, details)
        plan.accounts.set(accounts)
        for topic in details["topics"]:
            Topic.objects.create(plan=plan, name=topic["name"], preset=topic["preset"])
        save_rules(plan, rules)
        make_slots(plan)
    return get_plan(user, plan.id)


def replace_schedule(user, plan_id, rules):
    """Give a plan new schedule rules; remake its future slots that have not started."""
    plan = get_plan(user, plan_id)
    check_count_allowed(
        user, "posts_per_plan_per_day", most_posts_on_one_weekday(rules)
    )
    with transaction.atomic():
        remove_future_slots(plan)
        save_rules(plan, rules)
        make_slots(plan)
    return get_plan(user, plan.id)


def pause_plan(user, plan_id):
    """Stop a plan from posting; its waiting slots are removed."""
    plan = get_plan(user, plan_id)
    with transaction.atomic():
        plan.paused = True
        plan.save(update_fields=["paused"])
        remove_future_slots(plan)
    return get_plan(user, plan.id)


def resume_plan(user, plan_id):
    """Start a paused plan posting again (it counts as active again)."""
    plan = get_plan(user, plan_id)
    if not plan.paused:
        return plan
    check_total_limit(user, "active_plans", count_total_items(user, "active_plans"))
    with transaction.atomic():
        plan.paused = False
        plan.save(update_fields=["paused"])
        make_slots(plan)
    return get_plan(user, plan.id)


def get_upcoming_slots(user, plan_id):
    """Return the plan's slots from now on that are waiting or underway."""
    plan = get_plan(user, plan_id)
    return PostSlot.objects.filter(
        plan=plan,
        publish_at__gte=timezone.now(),
        status__in=["waiting", "claimed", "started"],
    ).select_related("post")


def delete_plan(user, plan_id):
    """Delete one of the user's plans and everything made for it."""
    get_plan(user, plan_id).delete()
