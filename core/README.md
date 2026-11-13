# core: shared building blocks

Small pieces that several apps use. Nothing in `core` depends on a feature app.

| File | What it does |
|---|---|
| `apps.py` | Tells Django this app exists. |
| `crypto.py` | `encrypt_text()` and `decrypt_text()` protect saved API keys. The only file that touches the cryptography library. |
| `errors.py` | `AppError`, the parent of all our expected errors; `problem_details_handler`, which gives every API error the same shape; and the provider errors: `ProviderError` (give up), `ProviderBusy` (try again later) and `ProviderKeyRejected` (the user must fix their key). |
| `serializers.py` | The shape of the health check's answer. |
| `services.py` | `is_database_reachable()`, used by the health check. |
| `tasks.py` | `check_worker_health`, a tiny background job that proves a worker is running. |
| `web.py` | The safe web client: `post_json`, `get_json`, `get_bytes`. The only file that uses httpx. Refuses private addresses (SSRF), never follows redirects, caps answer size, hides keys in error text, and turns failures into `ProviderBusy`, `ProviderKeyRejected` or `ProviderError`. |
| `urls.py` | The address `/api/v1/health/`. |
| `views.py` | `HealthView`, which answers the health check. |

**Main flow:** a request to `/api/v1/health/` reaches `HealthView.get()`, which calls `is_database_reachable()` and returns `{"status": "ok", "database": "ok"}`.
