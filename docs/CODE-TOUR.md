# Code Tour

A guided path through the code for someone who knows basic Python. Read the
sections in order; each one builds on the last. The rules every file follows
are in [design/code-standard.md](../design/code-standard.md).

## 1. Run it and try it

```bash
uv sync                               # install the exact package versions in uv.lock
docker compose up -d db redis         # start Postgres (port 5433) and Redis (port 6380)
uv run python manage.py migrate       # create the database tables
uv run python manage.py create_invite_codes 1
uv run python manage.py runserver     # API at http://localhost:8000
```

Open http://localhost:8000/api/v1/docs/ to click through every endpoint.
Run the tests with `uv run pytest`.

## 2. Reading order

1. `config/settings/base.py`: every setting, with comments.
2. `config/urls.py`: the list of web addresses. Each app adds its own.
3. `core/`: shared building blocks (errors, encryption, health check).
4. `accounts/`: users, invite codes, login with a cookie.
5. `quotas/`: free-tier limits.
6. `notifications/`: in-app messages.
7. `credentials/`: each user's own AI and news keys, stored encrypted.

Each app folder has a `README.md` that describes every file in it.

## 3. The shape of every app

Every app uses the same file names, so you always know where to look:

| File | Job |
|---|---|
| `models.py` | Database tables. |
| `serializers.py` | What goes in and out of the API. |
| `views.py` | Thin API classes: check input, call a service, return the result. |
| `urls.py` | Web addresses. |
| `services.py` | Plain functions that do the real work. |
| `tasks.py` | Background jobs (Celery). Each one just calls a service. |
| `tests/` | Tests, named as full sentences. |

**The flow only goes one way:** views call services, services call models.
Tasks call services too. Business rules never live in views or serializers.

## 4. The patterns we use (only these)

| Pattern | Where to see it |
|---|---|
| **Service function:** plain function, plain inputs, plain result | `accounts/services.py`, `register_user()` |
| **Our own error:** a subclass of `AppError` with a status, code and title | `quotas/services.py`, `QuotaExceeded` |
| **Task wrapper:** a Celery task that calls one service | `notifications/tasks.py` |
| **Quota check:** `check_total_limit()` or `use_daily_quota()` before the work | `quotas/services.py` |
| **Notification helper:** `notify(user, kind, message)` | `notifications/services.py` |
| **Library wrapper:** a library used in one file behind a simple function | `core/crypto.py` (`encrypt_text`) |
| **Adapter:** one base class, one subclass per provider | arrives with news, image and social providers |
| **Status table:** a dict of allowed status changes | arrives with posts |

## 5. One request, start to finish: logging in

`POST /api/v1/auth/login/` with `{"email": "...", "password": "..."}`

1. **`config/urls.py`** sends every `/api/v1/` address to the apps' url lists.
2. **`accounts/urls.py`** maps `auth/login/` to `LoginView`.
3. **`accounts/views.py`, `LoginView.post()`**
   - `PublicAuthView` (its parent) says: no login needed, at most 10 tries a minute.
   - `LoginSerializer` checks the email looks like an email and a password was sent.
4. **`accounts/services.py`, `log_in()`**
   - Django's `authenticate()` checks the password against the stored hash.
   - Wrong password: it raises `InvalidCredentials`, one of our `AppError`s.
   - Right password: it makes a refresh token and an access token.
5. **Back in the view**, the access token goes in the response body and
   `set_refresh_cookie()` puts the refresh token in an httpOnly cookie.
6. **If anything raised an `AppError`**, `core/errors.py` turns it into
   `{"status": 401, "code": "invalid_credentials", "title": ..., "detail": ...}`.

## 6. Glossary

| Word | Meaning |
|---|---|
| **API** | The set of web addresses a frontend calls to use the backend. |
| **Access token** | A short-lived pass (15 minutes) sent with each request: `Authorization: Bearer <token>`. |
| **Refresh token** | A longer-lived pass (7 days) kept in a cookie, used only to get a new access token. |
| **httpOnly cookie** | A cookie the browser stores but page scripts cannot read. |
| **Celery task** | A function that runs in the background, in a separate worker process. |
| **Celery Beat** | The timer that starts tasks on a schedule (for example every night). |
| **Migration** | A file that creates or changes database tables. |
| **Serializer** | Code that checks incoming data and shapes outgoing data. |
| **Throttling** | Refusing requests when someone sends too many too fast. |
| **Quota** | A free-tier limit, such as 6 posts per day. |
| **OpenAPI schema** | A machine-readable description of the API, saved in `schema/openapi.yaml`. |

## 7. Guardrails that keep the code honest

- `scripts/check_readability.py` and Ruff enforce the beginner code standard.
- `tests/test_celery_setup.py` checks every scheduled job names a real task.
- `tests/test_openapi_schema.py` stops the API changing by accident.
- `tests/test_code_tour.py` checks every app README lists all its files.
- `scripts/smoke_check.py` runs **inside the production Docker image** and
  checks the database, the message broker and the scheduled tasks. Unit tests
  run with development tools installed, which once hid a missing production
  package: every test passed, but the worker could not start. This check
  catches that kind of mistake.
