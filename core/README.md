# core: shared building blocks

Small pieces that several apps use. Nothing in `core` depends on a feature app.

| File | What it does |
|---|---|
| `apps.py` | Tells Django this app exists. |
| `crypto.py` | `encrypt_text()` and `decrypt_text()` protect saved API keys. The only file that touches the cryptography library. |
| `errors.py` | `AppError`, the parent of all our expected errors; `problem_details_handler`, which gives every API error the same shape; and `ProviderError`, raised when an outside service (AI model, news source, social network) fails. |
| `serializers.py` | The shape of the health check's answer. |
| `services.py` | `is_database_reachable()`, used by the health check. |
| `tasks.py` | `check_worker_health`, a tiny background job that proves a worker is running. |
| `urls.py` | The address `/api/v1/health/`. |
| `views.py` | `HealthView`, which answers the health check. |

**Main flow:** a request to `/api/v1/health/` reaches `HealthView.get()`, which calls `is_database_reachable()` and returns `{"status": "ok", "database": "ok"}`.
