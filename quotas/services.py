"""Check and use free-tier limits.

Two kinds of limits exist:
- "total" limits are about how many things exist right now, for example
  3 active plans. count_total_items() counts them, and the feature that
  owns them calls check_total_limit() before creating a new one.
- "day" limits are counters that start again at midnight in the user's own
  timezone, for example 10 posts per day. Call use_daily_quota() when the
  thing being limited actually happens.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import F
from django.utils import timezone

from core.errors import AppError
from planning.models import ContentPlan
from quotas.models import QuotaOverride, QuotaPolicy, QuotaUsage
from social.models import SocialAccount


class QuotaExceeded(AppError):
    """Raised when a user has reached one of their limits."""

    status = 403
    code = "quota_exceeded"
    title = "Limit reached"


class UnknownQuotaResource(Exception):
    """Raised when code asks about a limit that does not exist (a bug)."""


def get_policy(user, resource):
    """Return the QuotaPolicy for this user's tier and resource."""
    policy = QuotaPolicy.objects.filter(tier=user.tier, resource=resource).first()
    if policy is None:
        raise UnknownQuotaResource(f"No '{resource}' limit for tier '{user.tier}'.")
    return policy


def get_limit(user, resource):
    """Return the user's limit for a resource. An override wins over the tier."""
    override = QuotaOverride.objects.filter(user=user, resource=resource).first()
    if override is not None:
        return override.limit_value
    return get_policy(user, resource).limit_value


def local_today(user):
    """Return today's date in the user's own timezone."""
    return timezone.now().astimezone(ZoneInfo(user.timezone)).date()


def next_reset_time(user):
    """Return when daily limits start again: the user's next midnight."""
    tomorrow = local_today(user) + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=ZoneInfo(user.timezone))


def check_total_limit(user, resource, current_count):
    """Raise QuotaExceeded if the user already has as many as allowed."""
    limit = get_limit(user, resource)
    if current_count >= limit:
        description = get_policy(user, resource).description
        raise QuotaExceeded(
            f"You have reached your limit of {limit} for: {description}.",
            extra={"resource": resource, "limit": limit, "used": current_count},
        )


def count_total_items(user, resource):
    """Return how many of an account-wide "total" resource the user has now."""
    if resource == "active_plans":
        return ContentPlan.objects.filter(user=user, paused=False).count()
    if resource == "social_accounts":
        return SocialAccount.objects.filter(user=user).count()
    # Poster storage is measured when retention arrives in Phase 9.
    return 0


def check_count_allowed(user, resource, wanted_count):
    """Raise QuotaExceeded if wanted_count is more than the user's limit.

    Use it when several items are created at once, for example a plan with
    four topics. Having wanted_count items is fine when wanted_count - 1
    items still leave room for one more.
    """
    check_total_limit(user, resource, wanted_count - 1)


def get_daily_used(user, resource, scope=""):
    """Return how much of a daily limit the user has used today."""
    usage = QuotaUsage.objects.filter(
        user=user, resource=resource, scope=scope, day=local_today(user)
    ).first()
    if usage is None:
        return 0
    return usage.used


def use_daily_quota(user, resource, scope=""):
    """Count one use of a daily limit, or raise QuotaExceeded if none is left."""
    limit = get_limit(user, resource)
    usage, was_created = QuotaUsage.objects.get_or_create(
        user=user, resource=resource, scope=scope, day=local_today(user)
    )
    # Why this is here: one UPDATE that only succeeds while used < limit.
    # The database runs competing UPDATEs one at a time, so two requests can
    # never both take the last allowed use (see design/code-standard.md).
    updated_rows = QuotaUsage.objects.filter(id=usage.id, used__lt=limit).update(
        used=F("used") + 1
    )
    if updated_rows == 0:
        raise QuotaExceeded(
            f"You have used all {limit} for today. It starts again at midnight.",
            extra={
                "resource": resource,
                "limit": limit,
                "used": limit,
                "resets_at": next_reset_time(user).isoformat(),
            },
        )


def describe_usage(user, policy):
    """Return one limit and its current usage as a plain dictionary."""
    used = None
    resets_at = None
    if policy.applies_to == "account" and policy.period == "day":
        used = get_daily_used(user, policy.resource)
        resets_at = next_reset_time(user).isoformat()
    if policy.applies_to == "account" and policy.period == "total":
        used = count_total_items(user, policy.resource)
    return {
        "resource": policy.resource,
        "description": policy.description,
        "period": policy.period,
        "applies_to": policy.applies_to,
        "limit": get_limit(user, policy.resource),
        "used": used,
        "resets_at": resets_at,
    }


def get_usage_summary(user):
    """Return every limit on the user's tier with what they have used."""
    limits = []
    for policy in QuotaPolicy.objects.filter(tier=user.tier).order_by("resource"):
        limits.append(describe_usage(user, policy))
    return {"tier": user.tier, "limits": limits}
