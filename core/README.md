# core: shared building blocks

Small pieces that several apps use. Nothing in `core` depends on a feature app.

| File | What it does |
|---|---|
| `apps.py` | Tells Django this app exists. |
| `disk.py` | `disk_is_nearly_full()`: warns at 80% disk use and stops new posts and news reading at 90%, so a full disk fails safely. |
| `crypto.py` | `encrypt_text()` and `decrypt_text()` protect saved API keys. The only file that touches the cryptography library. |
| `errors.py` | `AppError`, the parent of all our expected errors; `problem_details_handler`, which gives every API error the same shape; and the provider errors: `ProviderError` (give up), `ProviderBusy` (try again later), `ProviderNoAnswer` (sent, but no answer: it may have acted) and `ProviderKeyRejected` (the user must fix their key). |
| `loadtest.py` | The local load test's helpers: a burst of due posts for throwaway demo users, progress, timings and clean-up. Run it with `python manage.py load_test --pipelines 100` (`management/commands/load_test.py`). |
| `maintenance.py` | `run_cleanup()`: the nightly retention rules (old posters, article text, records, link attempts), listed as a table at the top of the file. |
| `safe_network.py` | `CheckedNetwork`: every outside connection looks its host up once, refuses private addresses, and connects to that exact address, which stops DNS rebinding. The only file that uses httpcore. |
| `serializers.py` | The shape of the health check's answer. |
| `services.py` | `is_database_reachable()`, used by the health check. |
| `tasks.py` | `check_worker_health` (proves a worker is running) and `nightly_cleanup_task` (runs `run_cleanup` at 03:30). |
| `web.py` | The safe web client: `post_json`, `get_json`, `get_bytes`. The only file that uses httpx. Refuses private addresses (SSRF, checked again at connect time by `safe_network.py`), never follows redirects, caps answer size, hides keys in error text, and turns failures into `ProviderBusy`, `ProviderKeyRejected` or `ProviderError`. |
| `urls.py` | The address `/api/v1/health/`. |
| `views.py` | `HealthView`, which answers the health check. |

**Main flow:** a request to `/api/v1/health/` reaches `HealthView.get()`, which calls `is_database_reachable()` and returns `{"status": "ok", "database": "ok"}`.
