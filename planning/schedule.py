"""Turn schedule rules (local days and times) into PostSlot rows.

Rules are kept in local time ("09:00 in Asia/Kolkata"), and each slot is
saved in UTC. Two moments a year need care in places with daylight saving:

- Spring forward: the clocks jump, so a time such as 02:30 never happens
  that day. The slot moves to the next minute that does exist (03:00).
- Fall back: an hour happens twice, so 01:30 happens twice. The slot uses
  the first one.

make_slots() can run any number of times: the database allows only one slot
per plan and time, so running it again never creates duplicates.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from planning.models import PostSlot
from quotas.services import get_limit

ONE_MINUTE = timedelta(minutes=1)


def exists_on_the_clock(local_moment, zone):
    """Return True if local_moment (no timezone) really happens in zone."""
    as_utc = local_moment.replace(tzinfo=zone).astimezone(UTC)
    back_to_local = as_utc.astimezone(zone).replace(tzinfo=None)
    return back_to_local == local_moment


def local_to_utc(day, clock_time, zone_name):
    """Return the UTC moment of clock_time on day in the named timezone."""
    zone = ZoneInfo(zone_name)
    local_moment = datetime.combine(day, clock_time)
    # Spring forward: move to the next minute that exists. A gap is at most
    # a few hours, so this loop is short.
    while not exists_on_the_clock(local_moment, zone):
        local_moment = local_moment + ONE_MINUTE
    # fold=0 (the default) means "the first time" when an hour repeats.
    return local_moment.replace(tzinfo=zone).astimezone(UTC)


def parse_clock_time(text):
    """Turn "HH:MM" into a time."""
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def publish_times_for_rule(rule, first_day, day_count):
    """Return the UTC publish times of rule on day_count days from first_day."""
    publish_times = []
    for number in range(day_count):
        day = first_day + timedelta(days=number)
        if day.weekday() not in rule.days_of_week:
            continue
        for text in rule.times:
            publish_times.append(
                local_to_utc(day, parse_clock_time(text), rule.timezone)
            )
    return publish_times


def make_slots(plan, now=None):
    """Create the plan's slots from now until its schedule horizon.

    Returns how many slots were new. A paused plan gets no slots.
    """
    if now is None:
        now = timezone.now()
    if plan.paused:
        return 0
    horizon_days = get_limit(plan.user, "schedule_horizon_days")
    lead_time = timedelta(minutes=plan.lead_time_minutes)
    slots = []
    for rule in plan.schedule_rules.all():
        # Start a day early: in a timezone behind UTC, "today" may still be
        # yesterday there. Past times are dropped just below.
        first_day = now.astimezone(ZoneInfo(rule.timezone)).date() - timedelta(days=1)
        for publish_at in publish_times_for_rule(rule, first_day, horizon_days + 2):
            if now < publish_at <= now + timedelta(days=horizon_days):
                slots.append(
                    PostSlot(
                        plan=plan,
                        rule=rule,
                        publish_at=publish_at,
                        generate_at=publish_at - lead_time,
                    )
                )
    before = plan.slots.count()
    # ignore_conflicts: a slot that already exists is left as it is.
    PostSlot.objects.bulk_create(slots, ignore_conflicts=True)
    return plan.slots.count() - before


def remove_future_slots(plan, now=None):
    """Delete the plan's slots that have not started, so they can be remade."""
    if now is None:
        now = timezone.now()
    plan.slots.filter(status="waiting", publish_at__gt=now).delete()
