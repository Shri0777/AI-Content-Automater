"""Add the starting free-tier limits (plan.md, "Free limits per user").

These are starting values. The operator can change them later on the admin
site without a new release. The list lives here, not in app code, so this
migration always adds the same values no matter how the app changes later.
"""

from django.db import migrations

# (resource, limit, period, applies_to, description)
FREE_TIER_LIMITS = [
    ("active_plans", 3, "total", "account", "Active content plans"),
    ("topics_per_plan", 6, "total", "plan", "Topics in one content plan"),
    ("social_accounts", 5, "total", "account", "Linked social accounts"),
    ("posts_per_day", 6, "day", "account", "Posts generated per day"),
    ("posts_per_plan_per_day", 4, "day", "plan", "Posts per plan per day"),
    ("generate_now_per_day", 5, "day", "account", "Manual generate-now runs"),
    ("regenerations_per_post", 3, "total", "post", "Regenerations of one post"),
    ("credentials_per_kind", 1, "total", "kind", "Active keys of each kind"),
    ("news_previews_per_day", 30, "day", "account", "News preview requests"),
    ("poster_storage_mb", 250, "total", "account", "Poster storage in megabytes"),
    ("schedule_horizon_days", 14, "setting", "account", "Days scheduled ahead"),
    ("poster_retention_days", 30, "setting", "account", "Days posters are kept"),
]


def add_free_tier_limits(apps, schema_editor):
    """Create one QuotaPolicy row for each free-tier limit."""
    QuotaPolicy = apps.get_model("quotas", "QuotaPolicy")
    for resource, limit, period, applies_to, description in FREE_TIER_LIMITS:
        QuotaPolicy.objects.create(
            tier="free",
            resource=resource,
            limit_value=limit,
            period=period,
            applies_to=applies_to,
            description=description,
        )


def remove_free_tier_limits(apps, schema_editor):
    """Undo this migration by removing the free-tier rows."""
    QuotaPolicy = apps.get_model("quotas", "QuotaPolicy")
    QuotaPolicy.objects.filter(tier="free").delete()


class Migration(migrations.Migration):
    """Data migration that seeds the free-tier limits."""

    dependencies = [("quotas", "0001_initial")]

    operations = [
        migrations.RunPython(add_free_tier_limits, remove_free_tier_limits),
    ]
