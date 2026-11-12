# Bug Fix and Runtime Verification — AI Content Automater

**Repository:** `/home/shri/Development/AI-AUTOMATER`  
**Branch:** `main` (working tree clean; all changes committed in `V3`)  
**Task type:** Targeted reliability fixes (bug-fix preset), not a redesign.

---

## Root causes found

### Bug A — Invalid Django template filter (`|replace`)

**File:** `content/templates/content/generation_status.html` (line 28)

The template used:

```html
{{ content.generation_status|replace:"_"," "|title }}
```

Django does **not** provide a built-in `replace` template filter, so rendering the generation-status page raised:

```
TemplateSyntaxError: Invalid filter: 'replace'
```

This affected every generation status containing an underscore (`generating_text`, `generating_posters`, etc.).

### Bug B — Undefined `buffer_status` in create-page validation helper

**File:** `content/views/__init__.py`

`content_create()` computes `buffer_status` in its own scope but calls the POST helper as:

```python
return _handle_brief_create(request, buffer_profiles)
```

without passing `buffer_status`. When validation failed (empty brief, oversized brief, or unauthorized channel ID), `_handle_brief_create()` re-rendered `content/create.html` with:

```python
"buffer_status": buffer_status,
```

but `buffer_status` was **not defined** inside the helper, which would raise `NameError` on every validation failure.

### Runtime issue C — Redis / Celery background tasks

**Finding (environment):** Redis is **not installed** on this system and no Redis process is running (`redis-server`/`redis-cli` absent, `docker compose ps` empty, no `redis-server` process). The `content_create` view enqueues `generate_post_from_brief_task.delay()` inside a `try/except`:

```python
try:
    generate_post_from_brief_task.delay(content.pk)
except Exception:
    logger.warning("Could not enqueue generation task for content %s", content.pk)
```

As first implemented, a failed enqueue left the draft at `generation_status="queued"`, so it was never falsely reported as complete. However, this contained two real defects found on re-inspection:

1. **Initial enqueue failure made the draft permanently stuck.** A `"queued"` draft cannot be retried: `content_generate_retry` only accepts `failed`/`partial`. The original comment "the draft stays in 'queued' and the user can retry from the status page" was factually wrong — the status page's "Try again" form only renders for `failed`.
2. **Retry enqueue failure had the same flaw.** `content_generate_retry` persisted `queued` **before** calling `.delay()`; when enqueueing failed, the draft stayed `queued`, so the "Try again" button could never be used again, and the shown error alert ("Could not restart generation") contradicted the page's "Queued" status.

**Fix (2026-10-25):**
- Initial enqueue failure → persist `generation_status="failed"` and show `messages.error("Could not start generation. You can try again from the status page.")`.
- Retry enqueue failure → restore and persist `generation_status="failed"`; the error message was reworded from "Please try again later." to "Please try again." because retrying is immediately possible again.
- The misleading source comment in `content_create()` was corrected.

**Message visibility inspected:** `frontend/templates/frontend/base.html` includes `frontend/components/toast_container.html`, which renders every Django message as `alert alert-{{ message.tags }}`; CSS classes `.alert-error`/`.alert-success` exist in `frontend/static/frontend/css/components.css`; Django's default `MESSAGE_TAGS` (debug/info/success/warning/error) is not overridden. So the success/error feedback actually renders on the status page — confirmed by the regression tests asserting the alert text in the response body.

Regardless of enqueue failure, no duplicate versions or unsafe publishing can result, because the task body never runs when enqueueing fails, and the task sets `generation_status = "generating_text"` only when it actually executes. Redis/Docker runtime verification itself could **not** be performed (no Redis binaries, Docker services not running). See "Redis/Celery status" below.


### Integration issue D — Buffer authentication and public media URLs

**Finding (verified by reading code, no live calls):**

- Invalid/expired Buffer credentials are **not** treated as a successful connection. `BufferPublishingService.get_connection_status()` returns `connected: False`, `status: 'unauthorized'` on HTTP 401 / GraphQL `UNAUTHENTICATED`.
- Publishing does **not** proceed to unauthorized destinations. `BufferPublishingOrchestrator.execute_publishing()` validates every `profile_id` against the currently authorized set from `get_profiles()` and rejects unknown/unauthorized IDs with `unauthorized_destination` / `no_authorized_destinations`. Destination-verification failure causes the orchestrator to refuse dispatch (`destination_verification_failed`).
- A locally stored image is **not** represented as publicly reachable. `BufferPublishingService.create_update()` validates each image URL with `_is_public_https_url()` (rejects non-HTTPS, localhost, private/link-local addresses, credentials in URL) and `_is_reachable_image_url()` (requires an anonymous `HEAD` returning `200` with an `image/` content type). Local `/media/` URLs fail both checks.
- Public media storage requires Cloudflare R2: `MEDIA_STORAGE=r2` plus `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_DOMAIN`. When R2 is not configured, `MEDIA_URL='/media/'` (local) and Buffer image publishing is blocked by design.

Approval requirements, publication idempotency (`ContentPublication.idempotency_key` unique), ambiguous-outcome handling (no blind retry), and partial-failure recovery are all preserved. No live Buffer call was made.

### Noted inconsistency (documented, not changed)

The create page help text says "At least one destination is required for publishing," but creating a draft with **zero** selected channels is allowed (`target_channels=[]` is accepted). Publishing is gated elsewhere: `can_publish` in `content_detail()` requires `content.target_channels` to be truthy, and `execute_publishing()` requires at least one profile ID.

This is a reasonable draft-versus-publish separation (you can draft without channels, but cannot publish without them). The product rule was **not** changed, because the existing behavior is not incorrect and changing it is out of scope for this targeted fix.

---

## Files changed

### Fixes

| File | Change |
|------|--------|
| `content/views/__init__.py` | (1) Pass `buffer_status` into `_handle_brief_create()` so validation-error re-renders no longer raise `NameError`. (2) Add `GENERATION_STATUS_LABELS` mapping and `status_label` context variable in `content_generation_status()` to replace the invalid `|replace` template filter. Unknown statuses degrade gracefully via `status.replace("_", " ").title()`. |
| `content/templates/content/generation_status.html` | Replace `{{ content.generation_status\|replace:"_"," "|title }}` with `{{ status_label }}`. CSS class `status-{{ content.generation_status }}` (raw value) is preserved. |
| `content/views/__init__.py` (enqueue fix) | (3) Initial enqueue failure in `_handle_brief_create()` now persists `generation_status="failed"` and shows an error message; (4) retry enqueue failure in `content_generate_retry()` restores and persists `generation_status="failed"`; (5) corrected the stale comment about "queued is retryable"; (6) reworded the retry error message to "Please try again." |
| `content/tests/test_views.py` (enqueue fix) | Mocked the Celery enqueue in the two pre-existing create tests (`ContentCreateTest.test_created_content_automatically_owned_by_user`, `ContentCreateValidationTest.test_valid_brief_no_channels_redirects`). Their assertions had expected `'queued'` while the unmocked `.delay()` actually failed (no Redis) — exactly the falsified-state bug being fixed. The mock makes them hermetic; no assertion was weakened. |

### Regression tests added

| File | Coverage |
|------|----------|
| `content/tests/test_views.py` | New `ContentCreateValidationTest`: empty brief, oversized brief (>1,000 chars), unauthorized channel ID, valid brief with no channels (redirects), cross-user access rejection (403). New `ContentGenerationStatusTest`: readable labels for all underscore statuses (`generating_text`, `generating_posters`, etc.), graceful unknown-status degradation, retry button present on failed content. Buffer calls mocked via `unittest.mock.patch`; no real Buffer credentials. |
| `content/tests/test_views.py` (enqueue fix) | New `CeleryEnqueueFailureTest` (6 tests): initial `.delay()` failure → draft persists as `failed` + error alert rendered; successful initial enqueue → stays `queued`; retry `.delay()` failure → returns to `failed`; failed retry then successful retry → becomes `queued`; successful retry → `queued`; non-owner retry → 403 with no change and no enqueue. |

No existing tests were removed or weakened.

---

## Validation commands and results

All commands run with `venv/` (Python 3.12), which contains Django and Celery.

| Check | Command | Result |
|-------|---------|--------|
| Django system check | `venv/bin/python manage.py check` | PASS — no issues (0 silenced) |
| Migration consistency | `venv/bin/python manage.py makemigrations --check --dry-run` | PASS — no changes detected |
| Full test suite | `venv/bin/python manage.py test --keepdb --verbosity 1` | PASS — **423 tests, 0 failures** (OK); 417 at first fix, +6 for the enqueue-failure fix |
| Focused enqueue tests | `venv/bin/python manage.py test content.tests.test_views.CeleryEnqueueFailureTest --keepdb --verbosity 2` | PASS — **6 tests, 0 failures** (OK) |
| Targeted regression tests | `venv/bin/python manage.py test content.tests.test_views --keepdb -v 2` | PASS — 32 tests, 0 failures (OK); 26 at first fix, +6 for the enqueue-failure fix |
| `git diff --check` | `git diff --check` | PASS — exit 0 |
| Template compilation | `venv/bin/python -m py_compile content/views/__init__.py` | PASS |
| Dev server starts | `venv/bin/python manage.py runserver 127.0.0.1:8000` | PASS — server boots, create page returns 302 (redirect-to-login when unauthenticated, expected) |
| No `replace` filter remains | `grep -rn "|replace:" content/templates/ frontend/templates/` | PASS — none found |

**Test database:** reused the existing `--keepdb` test database (`test_ai_content_automater_dev`); no database was dropped, recreated, or reset.

**Tests mocked:** all Buffer and NVIDIA interactions are mocked in tests; no live external calls were made.

---

## Environment repair (2026-10-25)

**Problem:** the untracked `.venv/` directory (Python 3.14.8) could not import `celery` — running `.venv/bin/python manage.py check` fails with `ModuleNotFoundError: No module named 'celery'` raised from `content_automater/celery.py`.

**Diagnosis (inspected before changing anything):**

- The repository declares **two** dependency style sections in one root `requirements.txt`: exact pins (`Django==5.1.15`, `celery` is *not* in this section) followed by range pins (`celery[redis]>=5.3,<6.0`, `redis`, `django-celery-beat`, `Pillow`, `django-storages`, `boto3`, `gunicorn`, …).
- `.venv` contains **only the first section** — its package list matches the exact-pin section, and it is missing every package from the second section: `celery`, `redis`, `django-celery-beat`, `django-storages`, `boto3`, `gunicorn`. It also has `Pillow 13.0.0`, which is **outside** the declared `Pillow>=10.0,<11.0` range.
- `.venv` is referenced by **no repository documentation**, and Python 3.14 is outside the supported range for the pinned Django 5.1.x (README and Dockerfile both target Python 3.12).

**Intended environment (evidence):** `README.md` says `python3.12 -m venv venv` and `Dockerfile` says `FROM python:3.12-slim`. So the appropriate project environment is **`venv/`** (Python 3.12.14), not `.venv`.

**Resolution:**

- `venv/` was audited against the manifest with `pip check` and import checks: it was missing three declared dependencies — `gunicorn`, `django-storages`, `boto3` — so `venv/bin/python -m pip install -r requirements.txt` was run (satisfied pins are left untouched; only missing packages install). Installed: `gunicorn 21.2.0`, `django-storages 1.14.6`, `boto3 1.43.118` plus transitive `botocore/s3transfer/jmespath/python-dateutil 2.9.0.post0` (required by the declared `boto3>=1.35,<2.0`; no pins modified, no arbitrary versions).
- After repair: `venv/bin/pip check` → "No broken requirements found"; all declared packages import (`celery 5.6.3` within `>=5.3,<6.0`, `redis 5.3.1`, `django-celery-beat 2.9.0`, `Pillow 10.4.0` within `>=10.0,<11.0`).
- **`.venv` was left untouched** (no reset or recreate). Recommendation for the owner: either ignore/delete `.venv` or rebuild it as Python 3.12 from `requirements.txt`; as-is (Django 5.1.15 on Python 3.14, half-installed, Pillow out of range) it is not a supported configuration.
- **Documentation inconsistency found:** `README.md` references `requirements/development.txt`, which **does not exist** in the repository — the only manifest is the root `requirements.txt`. Left unchanged here (out of scope); noted for the owner.

## Redis/Celery status

| Item | Status | Detail |
|------|--------|--------|
| Redis installed | NOT VERIFIED (blocked) | `redis-server`/`redis-cli` not installed on this system; no Redis process running. |
| Redis process running | NOT VERIFIED (blocked) | No `redis-server` process found. |
| Docker services running | NOT VERIFIED (blocked) | `docker compose ps` returns no services. |
| `docker compose config` valid | PASS | `docker compose config --quiet` exits 0. |
| Enqueue failure handling | PASS (code reviewed + tests) | First implemented as "stay queued" — **that was a bug, now fixed**: on any enqueue failure the draft is persisted as `failed` (see the enqueue section below). No duplicate versions or false completion. |
| Safe command for later | — | `docker compose up -d redis` (then start worker/beat), or install and run `redis-server` locally on `localhost:6379`, matching `REDIS_URL=redis://localhost:6379/0` in `content_automater/settings/base.py`. |

The earlier log noise (`Retry limit exceeded while trying to reconnect to the Celery result store backend`) came from the test environment attempting to reach Redis, which is absent here. It is an environment limitation, not a code defect.

---

## Buffer/media status

| Item | Status | Detail |
|------|--------|--------|
| Invalid/expired Buffer credentials rejected | PASS (code reviewed) | `get_connection_status()` returns `connected: False, status: 'unauthorized'` on 401/`UNAUTHENTICATED`. |
| Unauthorized destinations rejected | PASS (code reviewed) | `execute_publishing()` validates `profile_ids` against `get_profiles()`; invalid IDs refused. |
| Local media URL not treated as public | PASS (code reviewed) | `_is_public_https_url()` + `_is_reachable_image_url()` block non-public/local image URLs. |
| Public media storage (R2) config | DOCUMENTED | Requires `MEDIA_STORAGE=r2` + R2 env vars; not configured locally, so Buffer image publishing is blocked by design with a clear UI message. |
| Live Buffer publish | NOT DONE | No live publication request was made (per safety rules). |
| Buffer token | NOT EXPOSED | No token values read, printed, or logged. |

---

## Browser verification

**Superseded (2026-10-26): real browser verification was completed in the final quality gate — see "Final quality gate (2026-10-26): real browser UX audit" below.**

| Item | Status | Detail |
|------|--------|--------|
| Playwright Python package | NOT VERIFIED (blocked) | `playwright` not installed in `venv/`; no Playwright browser automation available. |
| Django test client rendering | PASS | Generation-status and create pages render HTTP 200 for authenticated owners, verified by the new regression tests (readable labels, retry button, validation errors). |
| Dev server boot | PASS | `runserver` starts successfully; create page reachable (302 redirect-to-login when unauthenticated, expected). |

Browser verification through Playwright could not be performed at the time because the `playwright` Python package was not installed. The equivalent page-rendering behavior is covered by the Django test-client regression tests above.

---

## Remaining issues

1. **Redis/Celery runtime:** Redis is not installed or running, so background task enqueueing/processing could not be exercised end-to-end. The code path is safe on enqueue failure (graceful, retryable, no data loss — the draft is persisted as `failed` and the retry button works). To verify later: install/start Redis on `localhost:6379` (or `docker compose up -d redis`), then start the Celery worker and beat, and confirm a test task is processed.
2. **Browser/Playwright verification:** Not available in this environment. Covered by Django test-client tests instead.
3. **Noted inconsistency:** Create-page help text says "at least one destination is required," but drafts may be created with zero channels; publishing requires channels. Documented, not changed (out of scope for this targeted fix).
4. **Environment:** the untracked `.venv/` (Python 3.14, half-installed, Pillow out of declared range) remains unusable and untouched; the supported environment is `venv/` per README/Dockerfile. ~~`README.md` points to a nonexistent `requirements/development.txt` (only the root `requirements.txt` exists)~~ **RESOLVED (2026-10-25): the README setup command now installs from the root `requirements.txt`.**

---

## Comprehensive audit (2026-10-25)

Full runtime, UX, security, and release-readiness audit of the brief-first workflow.

### Audit finding 1 — Celery Beat schedule referenced unregistered task names (fixed)

**Root cause:** `CELERY_BEAT_SCHEDULE` in `content_automater/settings/base.py` referenced `'content.tasks.schedule_due_campaigns'` and `'content.tasks.reconcile_ambiguous_publications'`, but `@shared_task` registers tasks under the **full dotted path of the defining module**: `content.tasks.campaign_tasks.schedule_due_campaigns` and `content.tasks.publishing_tasks.reconcile_ambiguous_publications`. Verified against the live registry: both scheduled names resolve to `registered=False`. Beat would fail to find these tasks on every tick — the due-campaign scheduler and the ambiguous-publication reconciler would **never run**.

**Fix:** the two `'task'` values in `CELERY_BEAT_SCHEDULE` were corrected to the registered names, with a comment explaining the naming rule.

**Regression test (red-first):** `content/tests/test_celery_config.py` (`CeleryBeatScheduleTest.test_schedule_references_registered_task_names`) — failed before the fix with a clear message, passes after. Full suite after the fix: **424 tests, 0 failures**.

### Audit finding 2 — Misleading progress promise on the status page (fixed)

The generation-status page intro said "This page updates as each step completes," but nothing on the page auto-updates (no meta refresh, no polling). Reworded to "Reload this page to see the latest progress." — one line, truthful, no behavior change. No test asserted the old sentence. (A JS/meta auto-refresh could be added later if wanted; deliberately not introduced now.)

### Runtime verification performed (live, isolated)

With a **disposable Redis container** (`redis:7-alpine`, published only on `127.0.0.1:6379`, `--rm`, removed afterwards — the user's compose config was not modified):

| Step | Result |
|------|--------|
| Redis health | PASS — `docker exec audit-redis redis-cli ping` → `PONG` |
| Worker connects to intended broker | PASS — worker log: `Connected to redis://localhost:6379/0`, `celery@… ready` |
| All tasks registered | PASS — `[tasks]` block lists all 6, incl. `content.tasks.brief_tasks.generate_post_from_brief_task` |
| Harmless non-publishing task round-trip | PASS — `debug_task.delay()` enqueued (`id c985a7eb…`) → worker log `received` → `succeeded in 0.0005s` |
| Real broker-down enqueue failure | PASS — Redis stopped → `debug_task.delay()` raises `OperationalError: Error 111 connecting to localhost:6379. Connection refused.` (exactly the exception class the enqueue-failure fix handles) |
| **Beat schedule fires (live, post-fix)** | PASS — with worker + beat running against the disposable Redis, beat logged `Scheduler: Sending due task schedule-due-campaigns (content.tasks.campaign_tasks.schedule_due_campaigns)` and the worker executed it: `succeeded in 0.0128s: {'queued': 0}`. Pre-fix, this dispatch would have failed with an unregistered-task error. The second scheduled entry (`reconcile_ambiguous_publications`) was additionally executed by direct enqueue: `succeeded … {'resolved': 0, 'remaining': 0}` (expected no-op: 0 ambiguous publications in the dev DB; verified before the run) |
| Cleanup | PASS — beat, worker, and the disposable container were stopped/removed; no leftover processes; beat's schedule file kept in `/tmp/opencode` (no repo pollution) |

**Not exercised live (and why):** `generate_post_from_brief_task` against the real worker would invoke AI providers (risk of a live NVIDIA call) — its wiring is verified by task registration plus mocked tests. The compose `redis` service publishes **no host ports** (in-network only); host-side verification therefore used the isolated container described above. A full worker/beat run with the compose stack remains a **BLOCKED** end-to-end check until Redis is available persistently.

### Security and integration findings (code-level, no live calls)

- CSRF middleware enabled; `{% csrf_token %}` present in both state-changing templates (`generation_status.html` retry form, `detail.html` retry-poster form).
- Production settings: `DEBUG = False`; `SECRET_KEY`, DB credentials, and `ALLOWED_HOSTS` are `required=True`/enforced.
- Buffer client: every `requests` call carries `timeout=self.timeout`; tokens are only ever logged/returned masked (`mask_token`); 401 → `connected: False, status: 'unauthorized'`.
- Publishing orchestrator: rejects unverified destinations and refuses dispatch when destination verification fails.
- AI provider adapters (`ai_providers/services/*.py`): all HTTP calls are timeout-paired (4 calls / 4 timeouts per adapter, incl. `nvidia_flux_adapter`); the Twitter OAuth provider also passes timeouts (multi-line call — an initial flat grep was a false positive).
- View log messages contain IDs/messages only — no tokens or secrets.

### Audit finding 3 — Dead `can_publish` block in `content_detail` (removed)

`content_detail` computed `can_publish` once without channel/Buffer conditions, then unconditionally recomputed it (with them) further down — the first block had no effect. The dead block was removed; the authoritative eligibility computation is unchanged. Behavior verified by the full suite (424 tests).

### Audit finding 4 — Duplicate status-label mapping (deduplicated)

The view's `GENERATION_STATUS_LABELS` dict duplicated display names already declared in `Content.GENERATION_STATUS_CHOICES`. The view now derives labels from the model choices (`dict(Content.GENERATION_STATUS_CHOICES)`), keeping the title-case fallback for unknown statuses (still covered by the existing unknown-status regression test).

### Findings documented, not changed (evidence in the architecture sweep)

1. **Ambiguous-publication reconciliation is currently a conservative no-op.** `reconcile_ambiguous_publications` only resolves a publication if its provider implements `check_post_status`; no provider does (and the provider is instantiated with `access_token=None`). Ambiguous publications therefore persist until manual resolution — safe (never falsely resolved), but the task cannot resolve anything until a real status-lookup is implemented (needs a Buffer post-status API and credential fetching).
2. **Provider error strings stay internal.** The brief flow's status page renders only fixed strings; `gen_result.error` (which may carry provider details) reaches only the Celery result backend and logs. The campaign flow's error surfacing is pre-existing behavior; left unchanged.
3. **Cosmetic duplicates in `content/views/__init__.py`:** the Buffer status/profile fetch is duplicated between `content_create` and `content_detail` (the two connected-checks are equivalent given the service contract); some local re-imports shadow module-level imports; `page_obj.count` is monkey-patched with a lambda in `content_list` (works, but odd). Left as-is — behavior-preserving cleanups only, to avoid churn.
4. **`content_transition` GET fall-through:** the view body handles POST only; a GET reaches the trailing redirect. Harmless; adding `require_http_methods` would change GET behavior (302 → 405) for any existing links.
5. **`frontend_ui` app** exists with zero references and is not in `INSTALLED_APPS` — dead code, removal out of scope.
6. **`campaigns/detail.html:149`** renders `exec.image_media.file.url` directly; if the media has no file, the template silence-on-error produces an empty `src` (no crash). Minor; unverified visually.
7. **Failure alert shows the brief text** (`generation_status.html:16`) where a reason might be expected — autoescaped, no XSS; left as-is.

## How to understand the fix

**Bug A:** Django templates have no `|replace` filter. Instead of adding a custom filter (which would require registration and a new dependency-like concept), the view now computes a human-readable `status_label` from a small explicit mapping (`GENERATION_STATUS_LABELS`) and passes it to the template. The template renders `{{ status_label }}`. Unknown statuses fall back to `status.replace("_", " ").title()`. The CSS class still uses the raw `content.generation_status` value (underscores are fine in class names).

**Bug B:** `_handle_brief_create()` referenced `buffer_status` without receiving it. The fix threads `buffer_status` from `content_create()` into the helper as an explicit parameter, so every validation-error render receives all required template context (`buffer_status`, `buffer_profiles`, `errors`, `brief`, `context_notes`, `target_channels`).

**Enqueue failures:** `generation_status` must always match reality. If no task was enqueued, the truth is "failed", not "queued" — and the retry UI only works for `failed`/`partial`, so leaving `"queued"` freezes the user out of any retry. The rule is now: **persist `"queued"` only when `.delay()` actually succeeded; otherwise persist `"failed"`** (in both the initial-create and retry paths), and tell the user through a Django message (rendered globally by `frontend/components/toast_container.html`).

All fixes are minimal, use existing conventions, add no dependencies, and preserve all existing behavior for successful submissions and enqueues.

---

## Final quality gate (2026-10-26): real browser UX audit

Real-browser verification using the Playwright MCP (Firefox, no project dependency changes). Disposable Redis (`docker run --rm redis:7-alpine`, localhost-only), dev server on `127.0.0.1:8000` with `BUFFER_ACCESS_TOKEN`/`TEXT_API_KEY`/`IMAGE_API_KEY`/`GNEWS_API_KEY` **emptied via process env** so no live Buffer/NVIDIA/Google-News call was possible, and **no worker running** so enqueued tasks were never executed (the generation task never ran, so no AI provider was contacted).

### Automated re-checks (this date)

| Check | Command | Result |
|---|---|---|
| Full Django suite | `venv/bin/python manage.py test --keepdb` | **PASS — 428 tests, 0 failures** (was 424; +4 new: 2 heading, 1 doctype, 1 cross-user retry) |
| Focused: `ContentGenerationStatusTest` / `ContentAuthorizationTest` / `CeleryEnqueueFailureTest` / `content.tests.test_celery_config` | `manage.py test …` | PASS |
| System check | `manage.py check` | PASS (0 issues) |
| Migration check | `manage.py makemigrations --check --dry-run` | PASS (no changes) |
| Compose validation | `docker compose config --quiet` | PASS |
| Diff hygiene | `git diff --check` | PASS |

### Live Redis/Celery re-verification (disposable broker)

| Step | Result | Evidence |
|---|---|---|
| Redis health | PASS | `redis-cli ping` → PONG |
| Worker connect + registry | PASS | Connected to `redis://localhost:6379/0`; all 6 tasks registered (3 brief/campaign/publishing + debug_task) |
| Harmless round-trip | PASS | `debug_task` enqueued (id returned) → received → `succeeded in 0.0005s` |
| Beat dispatch | PASS | `Scheduler: Sending due task schedule-due-campaigns (content.tasks.campaign_tasks.schedule_due_campaigns)` → worker received → `{'queued': 0}` |
| Broker-down enqueue | PASS | `.delay()` with Redis stopped → `OperationalError: Error 111 connecting to localhost:6379. Connection refused.` (no false success) |
| Cleanup | PASS | Audit worker/beat stopped, disposable Redis containers removed, no repo pollution, no unrelated container touched |

### Real browser flows (Playwright MCP + Firefox)

| Flow | Result | Notes |
|---|---|---|
| Login page render | PASS | A11y tree clean; email-based login (app convention: `username == email`) |
| Empty brief | PASS (client guard) | Submit button disabled while brief is empty (`generate-btn.disabled = text.length === 0 \|\| text.length > 1000`); server-side validation additionally unit-tested |
| Oversized brief (>1000 chars) | PASS (client guard) | Button auto-disables; static hint "max 1,000 characters" shown. UX nit documented below |
| Valid brief → queued | PASS | Browser POST → draft persisted → **real `.delay()`** → status page truthfully shows **Queued** + "Reload this page…" wording; task physically verified in broker queue (`LLEN celery = 1`) |
| Broker-down create → failed | PASS | Draft persisted **Failed**; message "Could not start generation. You can try again from the status page."; **Try again** + **Edit brief** controls visible; brief preserved |
| Retry with broker down | PASS | Stays **Failed**, truthful message, retry remains possible |
| Retry after broker recovery | PASS | **"Generation restarted."** → **Queued** — the enqueue path recovers in the same server process without a restart |
| Cross-user access | PASS | Intruder GET on another user's status page → **403 Forbidden**, clean denial message; cross-user retry POST covered by new unit test |
| Responsive | PASS | 390×844: no horizontal overflow; controls intact |
| Console | PASS | 0 errors / 0 warnings on login, create, status pages (after fix 3 below) |
| Screenshots | Captured | `/tmp/opencode/status-{queued-desktop,failed-desktop,failed-mobile,failed-fixed-desktop,failed-fixed-mobile}.png` (outside the repo) |

### Defects found by the browser audit and fixed (with regression tests)

1. **Misleading heading on failed generations** — the status page hardcoded `<h1>Your post is being prepared</h1>` for every state, so a **failed** draft was headed as in-progress. Fixed by making the heading state-aware (`failed` → "Generation didn't finish", `complete` → "Your post is ready", else the in-progress wording). Regression: `ContentGenerationStatusTest.test_heading_matches_actual_state` (verified red against the old template, then green).
2. **Unlabelled brief echo in the failed alert** — the brief text ran on directly after "We couldn't generate your post." and could be misread as the failure reason. Now rendered as its own labelled paragraph (`Your brief: …`). Regression: `test_failed_alert_labels_the_brief`.
3. **403 page rendered in Quirks Mode** — `user_owns_content` returned a bare-string `HttpResponseForbidden` body (no `<!DOCTYPE html>`), so the browser warned "This page is in Quirks Mode". The denial is now a minimal full HTML document. Regression: `ContentAuthorizationTest.test_forbidden_response_is_a_full_html_document` + `test_unauthorized_user_cannot_retry_generation` (cross-user retry POST → 403, state unchanged).

### Operational observations (documented, not changed)

- **Broker-outage latency:** with Redis down, the create/retry request blocks ~20 s (kombu/django-redis reconnect loop, `Retry (n/20)`) before failing gracefully; the app then logs `CRITICAL … The Celery application must be restarted` from the reconnect monitor, but the actual publish path **recovers on the next attempt** (verified live: retry succeeded after Redis returned, same process). Users see a slow but truthful failure; no code change made.
- **Email-login convention:** `login_view` authenticates with `username=email`; registration creates users with `username == email` (`users/forms.py`). Users created by other paths (e.g. `createsuperuser` with a non-email username) cannot log in through the email form. A custom email auth backend would remove this fragility — future work.
- **Queued tasks are not persistent-proof in disposable brokers:** a queued generation in the disposable test Redis was lost when the container was replaced (test artifact). The production compose Redis is persistent (`--appendonly yes` + `redis_data` volume), so this does not apply to the deployed setup.
- **Oversized-brief UX:** the submit button silently disables at >1000 chars (only the static hint above the field explains why). A live character counter would help — future enhancement.
- Test data used by the audit (3 drafts, 2 users) was deleted from the dev database after verification; screenshots and logs live under `/tmp/opencode/` outside the repo.
