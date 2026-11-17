"""Start the scheduled posts whose time has come. Runs every minute.

Several dispatchers may run at once (two Beat processes, a restart), and a
worker may crash halfway. Three rules keep every slot started exactly once:

1. Claiming uses SELECT ... FOR UPDATE SKIP LOCKED: a slot one dispatcher
   is claiming is invisible to the others, instead of making them wait.
2. A claim is a lease (claimed_until). If the worker crashes, the lease runs
   out after LEASE and the next dispatcher claims the slot again.
3. A post can belong to only one slot (a one-to-one link), so even a slot
   claimed twice can never produce two posts.

A slot that cannot start within its plan's max_lateness after publish_at
(for example after the server was down) is skipped, never posted late, and
the owner gets one notification for the whole batch.
"""

import time
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.disk import disk_is_nearly_full
from core.errors import AppError
from notifications.services import notify
from planning.models import PostSlot
from quotas.services import QuotaExceeded
from studio.services import create_scheduled_post

LEASE = timedelta(minutes=5)
CLAIM_BATCH_SIZE = 50
# One run keeps claiming batches for at most this long, so it ends before
# Beat starts the next run a minute later. A load test with one batch per
# run left half of a 100-post burst waiting an extra minute.
RUN_TIME_BUDGET_SECONDS = 45
MISSED_WINDOW = "missed_window"


def free_to_claim(now):
    """Return due slots that nobody holds: waiting, or with a lapsed claim."""
    lapsed_claim = Q(status="claimed", claimed_until__lt=now)
    return PostSlot.objects.filter(generate_at__lte=now).filter(
        Q(status="waiting") | lapsed_claim
    )


def too_late(slot, now):
    """Return True if slot can no longer start in time to be worth posting."""
    allowed_delay = timedelta(minutes=slot.plan.max_lateness_minutes)
    return slot.publish_at + allowed_delay < now


def tell_owner_about_missed_slots(plan, count):
    """Send one notification about count skipped slots of plan."""
    notify(
        plan.user,
        "outage_missed_slots",
        f"{count} scheduled post(s) for '{plan.name}' were skipped because "
        "they could not start in time. Nothing was posted late.",
        related=plan,
        dedupe_key=f"missed-slots:{plan.id}",
    )


def skip_missed_slots(now):
    """Skip every free slot that is too late; return how many were skipped."""
    candidates = free_to_claim(now).filter(publish_at__lt=now)
    missed_by_plan = {}
    for slot in candidates.select_related("plan", "plan__user"):
        if too_late(slot, now):
            if slot.plan not in missed_by_plan:
                missed_by_plan[slot.plan] = []
            missed_by_plan[slot.plan].append(slot.id)
    total = 0
    for plan, slot_ids in missed_by_plan.items():
        # Filtering again means a slot claimed meanwhile is left alone.
        count = (
            free_to_claim(now)
            .filter(id__in=slot_ids)
            .update(status="skipped", skip_reason=MISSED_WINDOW, claimed_until=None)
        )
        if count > 0:
            tell_owner_about_missed_slots(plan, count)
        total = total + count
    return total


def claim_due_slots(now):
    """Claim up to CLAIM_BATCH_SIZE due slots; return their ids."""
    with transaction.atomic():
        # Named exception to the code standard (design/code-standard.md):
        # skip_locked hides rows another dispatcher is claiming right now.
        slots = list(
            free_to_claim(now)
            .select_for_update(skip_locked=True)
            .order_by("generate_at")[:CLAIM_BATCH_SIZE]
        )
        slot_ids = [slot.id for slot in slots]
        PostSlot.objects.filter(id__in=slot_ids).update(
            status="claimed", claimed_until=now + LEASE
        )
    return slot_ids


def skip_slot(slot, reason):
    """Mark a claimed slot skipped with a short reason."""
    PostSlot.objects.filter(id=slot.id, status="claimed").update(
        status="skipped", skip_reason=reason, claimed_until=None
    )


def start_slot(slot_id, now):
    """Start the post for one claimed slot. Return the post, or None if skipped."""
    slot = PostSlot.objects.select_related("plan", "plan__user").get(id=slot_id)
    if slot.plan.paused:
        skip_slot(slot, "plan_paused")
        return None
    if too_late(slot, now):
        skip_slot(slot, MISSED_WINDOW)
        tell_owner_about_missed_slots(slot.plan, 1)
        return None
    try:
        return create_scheduled_post(slot)
    except QuotaExceeded:
        skip_slot(slot, "quota_reached")
        notify(
            slot.plan.user,
            "quota_reached",
            f"A scheduled post for '{slot.plan.name}' was skipped: "
            "you reached today's post limit.",
            related=slot.plan,
            dedupe_key=f"quota-skip:{slot.plan.id}:{now.date()}",
        )
    except IntegrityError:
        # Another worker already made this slot's post: nothing to do.
        return None
    except AppError as error:
        skip_slot(slot, error.code)
    return None


def run_dispatcher(now=None):
    """Skip slots that are too late, then start every due slot.

    Returns {"started": ..., "skipped": ...} counts.
    """
    if now is None:
        now = timezone.now()
    skipped = skip_missed_slots(now)
    if disk_is_nearly_full():
        # No room for new posters: wait. Slots that wait too long are
        # skipped above with a notification, never posted late.
        return {"started": 0, "skipped": skipped}
    return {"started": start_due_slots(now), "skipped": skipped}


def start_due_slots(now):
    """Claim and start due slots, batch after batch; return how many started.

    Small batches keep each claim's lock short. Batches continue until no
    due slot is left or RUN_TIME_BUDGET_SECONDS have passed.
    """
    started = 0
    run_started = time.monotonic()
    while time.monotonic() - run_started < RUN_TIME_BUDGET_SECONDS:
        slot_ids = claim_due_slots(now)
        if not slot_ids:
            break
        for slot_id in slot_ids:
            if start_slot(slot_id, now) is not None:
                started = started + 1
    return started
