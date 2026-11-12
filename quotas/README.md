# quotas: free-tier limits

The product is free, so every user has limits (for example 6 posts a day).
Limits are rows in the database, so the operator can change them on the
admin site without a new release.

| File | What it does |
|---|---|
| `admin.py` | Lets the operator view and edit limits and per-user overrides. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `QuotaPolicy` (a tier's limit), `QuotaOverride` (one user's special limit), `QuotaUsage` (a daily counter). |
| `serializers.py` | The shape of the `/me/usage/` answer. |
| `services.py` | `get_limit`, `check_total_limit`, `use_daily_quota`, `get_usage_summary`. |
| `urls.py` | The address `/api/v1/me/usage/`. |
| `views.py` | `UsageView`, which shows a user their limits and usage. |

The starting limits are added by `migrations/0002_free_tier_limits.py`.

**Two kinds of limit:**
- *Total* limits count things that exist now (3 active plans). The feature
  that owns the things counts them and calls `check_total_limit()`.
- *Daily* limits are counters that start again at midnight in the user's own
  timezone. Call `use_daily_quota()` when the limited thing happens.

**Why the counter cannot be cheated:** `use_daily_quota()` adds one with a
single database UPDATE that only succeeds while `used < limit`. A test fires
20 requests at once and checks that exactly 6 succeed.
