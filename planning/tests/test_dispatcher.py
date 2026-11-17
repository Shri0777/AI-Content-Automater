"""The dispatcher starts each due slot once, survives crashes and outages."""

import threading
from datetime import timedelta

import pytest
from django.db import connection

from notifications.models import Notification
from planning.dispatcher import LEASE, run_dispatcher
from planning.models import PostSlot
from planning.tests.scheduling import utc
from quotas.models import QuotaOverride
from quotas.services import get_daily_used
from studio.models import Post

NOW = utc("2026-11-16 09:00")


def add_slot(plan, publish_at, status="waiting", claimed_until=None):
    """Save a slot publishing at publish_at that starts an hour before."""
    return PostSlot.objects.create(
        plan=plan,
        publish_at=publish_at,
        generate_at=publish_at - timedelta(hours=1),
        status=status,
        claimed_until=claimed_until,
    )


def test_a_due_slot_starts_one_post(plan):
    slot = add_slot(plan, NOW + timedelta(minutes=30))

    assert run_dispatcher(now=NOW) == {"started": 1, "skipped": 0}

    slot.refresh_from_db()
    assert slot.status == "started"
    post = Post.objects.get()
    assert post.slot == slot
    # Tests run background jobs at once, so the post is already made.
    assert post.status == "awaiting_approval"


def test_a_slot_whose_time_has_not_come_is_left_waiting(plan):
    add_slot(plan, NOW + timedelta(hours=3))

    assert run_dispatcher(now=NOW)["started"] == 0
    assert PostSlot.objects.get().status == "waiting"


def test_a_slot_claimed_by_a_crashed_worker_is_started_after_its_lease(plan):
    lapsed = NOW - timedelta(seconds=1)
    slot = add_slot(plan, NOW + timedelta(minutes=30), "claimed", lapsed)

    run_dispatcher(now=NOW)

    slot.refresh_from_db()
    assert slot.status == "started"
    assert Post.objects.filter(slot=slot).count() == 1


def test_a_slot_another_worker_still_holds_is_left_alone(plan):
    held_until = NOW + LEASE
    add_slot(plan, NOW + timedelta(minutes=30), "claimed", held_until)

    assert run_dispatcher(now=NOW)["started"] == 0
    assert not Post.objects.exists()


def test_after_an_outage_stale_slots_are_skipped_with_one_notification(plan):
    for hours_ago in [2, 3, 4, 5, 6]:
        add_slot(plan, NOW - timedelta(hours=hours_ago))
    recent = add_slot(plan, NOW - timedelta(minutes=10))

    counts = run_dispatcher(now=NOW)

    assert counts == {"started": 1, "skipped": 5}
    skipped = PostSlot.objects.filter(status="skipped")
    assert set(skipped.values_list("skip_reason", flat=True)) == {"missed_window"}
    notifications = Notification.objects.filter(kind="outage_missed_slots")
    assert notifications.count() == 1
    assert notifications[0].message.startswith("5 scheduled post(s)")
    recent.refresh_from_db()
    assert recent.status == "started"
    # Skipped slots never count towards the daily limit.
    assert get_daily_used(plan.user, "posts_per_day") == 1


def test_a_second_outage_run_does_not_repeat_the_notification(plan):
    add_slot(plan, NOW - timedelta(hours=2))
    run_dispatcher(now=NOW)
    add_slot(plan, NOW - timedelta(hours=1))

    run_dispatcher(now=NOW)

    assert Notification.objects.filter(kind="outage_missed_slots").count() == 1


def test_a_slot_over_the_daily_limit_is_skipped_and_the_owner_told(plan, user):
    QuotaOverride.objects.create(user=user, resource="posts_per_day", limit_value=0)
    add_slot(plan, NOW + timedelta(minutes=30))

    run_dispatcher(now=NOW)

    slot = PostSlot.objects.get()
    assert slot.status == "skipped"
    assert slot.skip_reason == "quota_reached"
    assert Notification.objects.filter(kind="quota_reached").count() == 1
    assert not Post.objects.exists()


def test_a_slot_of_a_plan_paused_meanwhile_is_skipped(plan):
    add_slot(plan, NOW + timedelta(minutes=30))
    plan.paused = True
    plan.save()

    run_dispatcher(now=NOW)

    assert PostSlot.objects.get().skip_reason == "plan_paused"
    assert not Post.objects.exists()


def dispatch_and_close():
    """Run the dispatcher in a worker thread, then close its database link."""
    run_dispatcher(now=NOW)
    connection.close()


# serialized_rollback puts back the rows migrations add (such as the free
# limits), which an earlier transactional test may have emptied.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_dispatchers_running_at_once_start_every_slot_exactly_once(plan, user):
    QuotaOverride.objects.create(user=user, resource="posts_per_day", limit_value=50)
    QuotaOverride.objects.create(
        user=user, resource="posts_per_plan_per_day", limit_value=50
    )
    for minutes in range(10, 30):
        add_slot(plan, NOW + timedelta(minutes=minutes))
    threads = []
    for _ in range(3):
        threads.append(threading.Thread(target=dispatch_and_close))

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert Post.objects.count() == 20
    assert PostSlot.objects.filter(status="started").count() == 20


def test_a_burst_bigger_than_one_batch_is_started_in_one_run(plan, user, monkeypatch):
    monkeypatch.setattr("planning.dispatcher.CLAIM_BATCH_SIZE", 3)
    QuotaOverride.objects.create(user=user, resource="posts_per_day", limit_value=50)
    QuotaOverride.objects.create(
        user=user, resource="posts_per_plan_per_day", limit_value=50
    )
    for minutes in range(10, 18):
        add_slot(plan, NOW + timedelta(minutes=minutes))

    assert run_dispatcher(now=NOW)["started"] == 8
