"""Raise the free tier to 10 posts a day.

posts_per_day (whole account), posts_per_plan_per_day (each plan) and
generate_now_per_day ("Make a post now") all go to 10, so one plan can
really make 10 posts a day; raising only one would leave the others to stop
it first. Undoing this restores the old values (6, 4 and 5).
"""

from django.db import migrations

NEW_LIMITS = {"posts_per_day": 10, "posts_per_plan_per_day": 10, "generate_now_per_day": 10}
OLD_LIMITS = {"posts_per_day": 6, "posts_per_plan_per_day": 4, "generate_now_per_day": 5}


def set_limits(apps, limits):
    """Set the free tier's limit for each resource in limits."""
    QuotaPolicy = apps.get_model("quotas", "QuotaPolicy")
    for resource, value in limits.items():
        QuotaPolicy.objects.filter(tier="free", resource=resource).update(
            limit_value=value
        )


def raise_limits(apps, schema_editor):
    """Move the three post limits to 10."""
    set_limits(apps, NEW_LIMITS)


def restore_limits(apps, schema_editor):
    """Put the three post limits back to their earlier values."""
    set_limits(apps, OLD_LIMITS)


class Migration(migrations.Migration):
    dependencies = [("quotas", "0002_free_tier_limits")]

    operations = [migrations.RunPython(raise_limits, restore_limits)]
