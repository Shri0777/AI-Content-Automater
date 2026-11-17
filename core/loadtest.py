"""A local load test: a burst of scheduled posts, all due at the same moment.

It models the free launch's busiest minute: many plans posting "at 09:00".
Run it inside the Docker stack with the real Beat, dispatcher and workers:

    docker compose exec web python manage.py load_test --pipelines 100

It only works in demo mode (fake AI and social providers), so it costs
nothing and contacts no one. It creates throwaway users named
"loadtest-...@example.invalid", waits for every post to be made, reports
the numbers, and deletes the users again.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from credentials.services import save_credential
from planning.models import ContentPlan, PostSlot, Topic
from quotas.models import QuotaOverride
from social.models import SocialAccount
from studio.models import Post

SLOTS_PER_PLAN = 4
# Matches the design's busiest case: posts are due to go out 20 minutes later.
PUBLISH_AFTER = timedelta(minutes=20)
FINISHED = ["awaiting_approval", "approved", "published", "skipped", "failed"]


def make_load_user(run_id, number):
    """Create one throwaway user with demo keys, a demo account and a plan."""
    user = get_user_model().objects.create_user(
        email=f"loadtest-{run_id}-{number}@example.invalid",
        password=uuid.uuid4().hex,
    )
    save_credential(user, {"kind": "text", "adapter": "demo"})
    save_credential(user, {"kind": "image", "adapter": "demo"})
    plan = ContentPlan.objects.create(user=user, name="Load test", paused=True)
    plan.accounts.add(
        SocialAccount.objects.create(
            user=user, platform="demo", display_name="Demo", external_id=run_id
        )
    )
    Topic.objects.create(plan=plan, name="AI", preset="ai_news")
    QuotaOverride.objects.create(user=user, resource="posts_per_day", limit_value=50)
    return plan


def make_burst(pipelines):
    """Create the users and due slots for a burst; return (run id, plans)."""
    run_id = uuid.uuid4().hex[:8]
    now = timezone.now()
    plans = []
    for number in range((pipelines + SLOTS_PER_PLAN - 1) // SLOTS_PER_PLAN):
        plan = make_load_user(run_id, number)
        for slot_number in range(SLOTS_PER_PLAN):
            publish_at = now + PUBLISH_AFTER + timedelta(seconds=slot_number)
            PostSlot.objects.create(plan=plan, publish_at=publish_at, generate_at=now)
        plans.append(plan)
    # Unpaused last, so the dispatcher sees the whole burst at once.
    ContentPlan.objects.filter(id__in=[plan.id for plan in plans]).update(paused=False)
    return run_id, plans


def database_connections():
    """Return how many connections the database has open right now."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_stat_activity")
        return cursor.fetchone()[0]


def progress(plans):
    """Return {status: count} for the burst's posts."""
    counts = {}
    for post in Post.objects.filter(plan__in=plans):
        counts[post.status] = counts.get(post.status, 0) + 1
    return counts


def count_finished(counts):
    """Return how many posts reached a finished or waiting status."""
    finished = 0
    for status in FINISHED:
        finished = finished + counts.get(status, 0)
    return finished


def percentile(values, share):
    """Return the value below which share (0 to 1) of the values fall."""
    ordered = sorted(values)
    if not ordered:
        return 0
    index = min(len(ordered) - 1, int(share * len(ordered)))
    return ordered[index]


def timings(plans):
    """Return claim lag and making time (seconds) for each finished post."""
    claim_lags = []
    making_times = []
    for post in Post.objects.filter(plan__in=plans).select_related("slot"):
        claim_lags.append((post.created_at - post.slot.generate_at).total_seconds())
        making_times.append((post.updated_at - post.created_at).total_seconds())
    return claim_lags, making_times


def delete_burst(run_id):
    """Delete the throwaway users (and, with them, everything they made)."""
    users = get_user_model().objects.filter(email__startswith=f"loadtest-{run_id}-")
    count = users.count()
    users.delete()
    return count
