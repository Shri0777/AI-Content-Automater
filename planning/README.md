# planning: content plans, their topics and their schedules

A plan says **what** to post about (topics and free-text requirements),
**where** (linked social accounts), **how** posts are approved, and **when**
(schedule rules).

| File | What it does |
|---|---|
| `admin.py` | Shows plans, with their topics, on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `dispatcher.py` | `run_dispatcher`: every minute, skips slots that are too late (one notification per plan), then claims due slots with `SKIP LOCKED` and a 5-minute lease, and starts their posts. |
| `models.py` | `ContentPlan`, `Topic`, `ScheduleRule` (weekdays, local times, timezone) and `PostSlot` (one planned post: `publish_at`, `generate_at`, status and claim). |
| `schedule.py` | `local_to_utc` (daylight-saving rules), `make_slots` (rules to slots up to the 14-day horizon, safe to repeat) and `remove_future_slots`. |
| `serializers.py` | What goes in and out of the API, including schedule rules (checked: weekdays 0 to 6, `HH:MM` times, a real timezone) and slots. |
| `services.py` | `create_plan`, `replace_schedule`, `pause_plan`, `resume_plan`, `get_upcoming_slots`, `get_plans`, `get_plan` and `delete_plan`. Limits checked: active plans, topics per plan and posting times per day. |
| `tasks.py` | `make_slots_task` (hourly) and `run_scheduler_task` (every minute: dispatcher, publish due posts, expire late ones). |
| `urls.py` | `/api/v1/plans/`, `<id>/`, `<id>/schedule/`, `<id>/pause/`, `<id>/resume/` and `<id>/upcoming/`. |
| `views.py` | Thin API classes. |

**A slot's life:**

```
waiting --(generate_at arrives, dispatcher claims it)--> claimed --> started (its post is made)
   |                                                        |
   +--(too late after an outage, plan paused, limit reached)+--> skipped
```

- **Times are local.** A rule says "Mondays at 09:00 in Asia/Kolkata". Each
  slot is saved in UTC. When clocks spring forward, a time that does not
  exist moves to the next minute that does; when they fall back, the first
  of the two times is used.
- **Exactly once.** `UNIQUE(plan, publish_at)` stops duplicate slots; the
  claim with `SKIP LOCKED`, the lease, and the one-to-one link from a post to
  its slot stop duplicate posts, even with several dispatchers or a crash.
- **Never stale.** A slot that cannot start within `max_lateness_minutes`
  of its time is skipped, not posted late, and does not count towards the
  daily limit.

**Approval modes:** `manual` (the default) asks before every post. `auto`
posts on its own only when the auto-post gate allows it
(`publishing/gate.py`): a clean pass with no issues, a total review score of
at least `auto_post_min_score` (default 22 of 25), and perfect scores on
strict topics. Anything else still waits for approval, with the reason.
