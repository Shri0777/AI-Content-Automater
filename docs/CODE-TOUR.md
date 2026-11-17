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

To watch a whole post being made, start the worker too
(`uv run celery -A config worker`) and run
`uv run python scripts/demo_walkthrough.py --invite-code <code>` with a code
from `create_invite_codes`. Development runs in **demo mode**: fake AI, news
and social providers (`demo/`), so no API keys are needed.

## 2. Reading order

1. `config/settings/base.py`: every setting, with comments.
2. `config/urls.py`: the list of web addresses. Each app adds its own.
3. `core/`: shared building blocks (errors, encryption, health check).
4. `accounts/`: users, invite codes, login with a cookie.
5. `quotas/`: free-tier limits.
6. `notifications/`: in-app messages.
7. `credentials/`: each user's own AI and news keys, stored encrypted.
8. `social/`: linked social accounts, the `Publisher` base class, one
   publisher per platform (Buffer, X, LinkedIn, Facebook) and token refresh.
9. `planning/`: content plans, topics and schedules: rules become slots
   (`schedule.py`), and the dispatcher starts them on time (`dispatcher.py`).
10. `newsroom/`: keyless news sources (RSS, Hacker News), polite fetching,
    the shared article store and the quality gates that choose an article.
11. `studio/`: the post pipeline (with up to 2 correction rounds), the status
    table, the poster renderer and the prompt-injection guards.
12. `publishing/`: sending approved posts, never twice; the auto-post gate;
    and settling posts a platform never confirmed.
13. `demo/`: the fake providers used in demo mode and by the tests.

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
| **Library wrapper:** a library used in one file behind a simple function | `core/crypto.py` (`encrypt_text`), `core/web.py` (httpx), `studio/anthropic_text.py` (anthropic), `studio/posters.py` (Pillow) |
| **Adapter:** one base class, one subclass per provider | `studio/text_models.py` with `studio/openai_compatible.py`, `studio/anthropic_text.py` and `demo/text_model.py`; also image models, `social/publishers.py`, `newsroom/sources.py` |
| **Status table:** a dict of allowed status changes | `studio/statuses.py`, `ALLOWED_TRANSITIONS` and `change_status()` |

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

## 6. One post, start to finish

`POST /api/v1/plans/<id>/generate-now/`

1. **`studio/views.py`, `GenerateNowView.post()`** calls
   `services.start_generation()`.
2. **`studio/services.py`, `start_generation()`** checks the plan is the
   user's and not paused, that text and image keys are saved, and picks the
   topic with the fewest posts. Inside one database transaction it uses three
   daily limits and creates a `Post` with status `researching`. If any limit
   is reached, the transaction is undone, so nothing is counted. Then it
   queues `advance_post_task` and the API answers `202 Accepted`.
3. **`studio/tasks.py`, `advance_post_task`** (in the worker) calls
   `run_stage()`, then queues itself again until the post waits for the user.
4. **`studio/runner.py`, `run_stage()`** looks up the stage for the post's
   status in `STAGES` (`studio/pipeline.py`) and runs it:
   - `research`: `newsroom.services.pick_article()` finds a fresh, unused
     article, or the post is **skipped** (never filler).
   - `draft`: the text model writes the headline and caption.
   - `make_poster`: the text model writes an image prompt, the image model
     makes artwork, and `render_poster()` adds the headline.
   - `review`: the text model scores the post, `decide_verdict()` applies
     fixed rules, and `notify()` tells the user it is waiting.
   Every stage run saves a `GenerationStep` (models used, prompt versions,
   tokens). A busy provider is retried later; a refused key marks the
   credential `invalid`; any other `ProviderError` fails the post with a
   plain reason. The user is told in each case.
   Real models are called through `TextModel.ask_for_json()`
   (`studio/text_models.py`), which fills in a prompt from
   `studio/prompts.py`, checks the JSON answer with `studio/model_outputs.py`
   and asks once more if it does not fit.
5. **The user approves:** `POST /api/v1/posts/<id>/approve/` calls
   `change_status(post, "approved")`. Two clicks at once cannot both win,
   because the database update only matches the old status.
6. **`publishing/services.py`, `publish_post()`** sends the post to each of
   the plan's accounts with the AI label added, cut to each network's
   caption limit. The unique `idempotency_key` means each account is
   contacted at most once. Just before posting, `social/tokens.py`,
   `refresh_account()` renews a token that is about to end; a token the
   platform refuses marks the account `needs_reauth` and tells the user.

You can follow all of this in the API: `GET /api/v1/posts/<id>/` shows the
article, versions, review, steps and publications.

## 7. Glossary

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
| **Adapter** | One base class with one subclass per outside service, so the rest of the code never knows which service it uses. |
| **Demo mode** | `DEMO_MODE=true`: fake providers stand in for every outside service, so no API keys are needed. |
| **Pipeline stage** | One step of making a post (research, draft, poster, review), run as one background job. |
| **Idempotency key** | A value that is always the same for the same action, so the action can be safely retried without happening twice. |
| **SSRF** | Tricking a server into calling addresses inside its own network. `core/web.py` refuses private addresses. |
| **OAuth** | The "Log in with X / LinkedIn / Facebook" approval flow. The platform hands us a code, which we swap for tokens (`social/oauth.py`). |
| **State (OAuth)** | A random, single-use value sent to the platform and checked when the user comes back, so another site cannot link its account to our user. |
| **PKCE** | Sending a fingerprint of a secret first and the secret itself only when swapping the code, so a stolen code is useless. |
| **Row lock** | `select_for_update()` makes a second worker wait for the first, so a once-only refresh token is never used twice (`social/tokens.py`). |
| **Signed link** | An address that carries a signature made with our secret key, so it cannot be guessed or changed (`studio/public_links.py`). |
| **Auto-post gate** | The one function that decides if a post may go out without the owner's approval (`publishing/gate.py`). Closed unless every rule passes. |
| **Ambiguous** | A post we sent but never got an answer for: it may or may not be live, so it is never re-sent automatically (`publishing/reconcile.py`). |
| **Prompt injection** | Text from the internet that tries to give the AI orders. Kept inside `<article>` tags, defused, and caught by `studio/guards.py`. |
| **Golden image** | An approved reference picture a test compares new output against (`studio/tests/golden/`). |
| **RSS / Atom feed** | A site's machine-readable list of its newest articles (`newsroom/feeds.py`). |
| **robots.txt** | A file where a site says which automated readers may read which pages. We obey it (`newsroom/fetching.py`). |
| **Ingest** | Reading every source of a topic into the shared article store (`newsroom/ingest.py`). |
| **Slot** | One planned post: when it is published (`publish_at`) and when making it starts (`generate_at`). `planning/models.py`, `PostSlot`. |
| **Dispatcher** | The every-minute job that starts due slots (`planning/dispatcher.py`). |
| **Lease** | A claim that runs out on its own (`claimed_until`), so a crashed worker cannot hold a slot forever. |
| **SKIP LOCKED** | A database option that makes rows another worker has locked invisible instead of making everyone wait. |
| **Daylight saving** | Clocks moving an hour in spring and autumn. Schedules are kept in local time, so 09:00 stays 09:00 (`planning/schedule.py`). |
| **Stub server** | A small fake web service used in tests that answers like a real provider (`tests/stub_server.py`). |
| **OpenAPI schema** | A machine-readable description of the API, saved in `schema/openapi.yaml`. |

## 8. Guardrails that keep the code honest

- `scripts/check_readability.py` and Ruff enforce the beginner code standard.
- `tests/test_celery_setup.py` checks every scheduled job names a real task.
- `tests/test_openapi_schema.py` stops the API changing by accident.
- `tests/test_code_tour.py` checks every app README lists all its files.
- `scripts/smoke_check.py` runs **inside the production Docker image** and
  checks the database, the message broker and the scheduled tasks. Unit tests
  run with development tools installed, which once hid a missing production
  package: every test passed, but the worker could not start. This check
  catches that kind of mistake.
