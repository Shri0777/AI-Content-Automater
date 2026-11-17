"""Turning local schedule rules into UTC slots, including daylight saving.

The daylight-saving dates below are 2026's, as Python's timezone database
(zoneinfo) gives them:
- New York: clocks jump 02:00 -> 03:00 on 8 March, go back 02:00 -> 01:00
  on 1 November.
- London: 01:00 -> 02:00 on 29 March, 02:00 -> 01:00 on 25 October.
- Sydney (southern summer): 02:00 -> 03:00 on 4 October, 03:00 -> 02:00 on
  5 April.
- Kolkata: no daylight saving.
"""

from datetime import date, time

import pytest

from planning.models import PostSlot
from planning.schedule import local_to_utc, make_slots, remove_future_slots
from planning.tests.scheduling import add_rule, utc


@pytest.mark.parametrize(
    "case, day, clock, zone, expected",
    [
        (
            "ordinary day, no DST zone",
            date(2026, 3, 8),
            time(9, 0),
            "Asia/Kolkata",
            "2026-03-08 03:30",
        ),
        (
            "New York winter",
            date(2026, 3, 7),
            time(2, 30),
            "America/New_York",
            "2026-03-07 07:30",
        ),
        (
            "New York spring-forward gap moves to 03:00",
            date(2026, 3, 8),
            time(2, 30),
            "America/New_York",
            "2026-03-08 07:00",
        ),
        (
            "New York just after the gap",
            date(2026, 3, 8),
            time(3, 30),
            "America/New_York",
            "2026-03-08 07:30",
        ),
        (
            "New York fall-back repeat uses the first 01:30",
            date(2026, 11, 1),
            time(1, 30),
            "America/New_York",
            "2026-11-01 05:30",
        ),
        (
            "London spring-forward gap moves to 02:00",
            date(2026, 3, 29),
            time(1, 15),
            "Europe/London",
            "2026-03-29 01:00",
        ),
        (
            "London fall-back repeat uses the first 01:30",
            date(2026, 10, 25),
            time(1, 30),
            "Europe/London",
            "2026-10-25 00:30",
        ),
        (
            "Sydney spring-forward gap in October",
            date(2026, 10, 4),
            time(2, 45),
            "Australia/Sydney",
            "2026-10-03 16:00",
        ),
        (
            "Sydney fall-back repeat in April",
            date(2026, 4, 5),
            time(2, 30),
            "Australia/Sydney",
            "2026-04-04 15:30",
        ),
    ],
)
def test_local_times_become_the_right_utc_moment(case, day, clock, zone, expected):
    assert local_to_utc(day, clock, zone) == utc(expected), case


def test_slots_are_made_for_the_chosen_weekdays_and_times(plan):
    # Mondays and Thursdays at 09:00 and 18:00 Kolkata time (UTC+5:30).
    add_rule(plan, [0, 3], ["09:00", "18:00"], "Asia/Kolkata")
    monday_morning = utc("2026-11-16 00:00")

    make_slots(plan, now=monday_morning)

    first_four = list(PostSlot.objects.values_list("publish_at", flat=True)[:4])
    assert first_four == [
        utc("2026-11-16 03:30"),
        utc("2026-11-16 12:30"),
        utc("2026-11-19 03:30"),
        utc("2026-11-19 12:30"),
    ]


def test_slots_reach_exactly_the_schedule_horizon_of_14_days(plan):
    add_rule(plan, [0, 1, 2, 3, 4, 5, 6], ["12:00"], "UTC")

    make_slots(plan, now=utc("2026-11-16 13:00"))

    slots = list(PostSlot.objects.all())
    assert len(slots) == 14
    assert slots[0].publish_at == utc("2026-11-17 12:00")
    assert slots[-1].publish_at == utc("2026-11-30 12:00")


def test_making_slots_twice_never_duplicates_them(plan):
    add_rule(plan, [0, 3], ["09:00"], "Asia/Kolkata")
    now = utc("2026-11-16 00:00")

    first = make_slots(plan, now=now)
    second = make_slots(plan, now=now)

    assert first == 4
    assert second == 0
    assert PostSlot.objects.count() == 4


def test_each_slot_starts_lead_time_before_it_is_published(plan):
    plan.lead_time_minutes = 90
    plan.save()
    add_rule(plan, [0], ["09:00"], "UTC")

    make_slots(plan, now=utc("2026-11-16 00:00"))

    slot = PostSlot.objects.first()
    assert slot.generate_at == utc("2026-11-16 07:30")


def test_a_paused_plan_gets_no_slots(plan):
    plan.paused = True
    plan.save()
    add_rule(plan, [0], ["09:00"], "UTC")

    assert make_slots(plan, now=utc("2026-11-16 00:00")) == 0


def test_changing_a_schedule_remakes_only_slots_that_have_not_started(plan):
    rule = add_rule(plan, [0, 1, 2, 3, 4, 5, 6], ["12:00"], "UTC")
    now = utc("2026-11-16 00:00")
    make_slots(plan, now=now)
    started = PostSlot.objects.first()
    started.status = "started"
    started.save()

    remove_future_slots(plan, now=now)
    rule.times = ["15:00"]
    rule.save()
    make_slots(plan, now=now)

    times = set(PostSlot.objects.values_list("publish_at__hour", flat=True))
    assert times == {12, 15}
    assert PostSlot.objects.filter(publish_at__hour=12).get().status == "started"
