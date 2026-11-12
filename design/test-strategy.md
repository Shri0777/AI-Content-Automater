# Test Strategy (V4 backend)

Goal: tests that exercise the **real wiring**. The V3 app had hundreds of passing tests and still failed on its first real runs, because they mocked the paths that broke. Related: [system-design.md](system-design.md).

## 1. Principles
1. **Test behaviour at the boundary that matters.** Prefer real Postgres, a real Celery worker and an HTTP stub server over mocks of our own code.
2. **Stubs speak the real wire format.** Provider stubs (LLM, image, news, Buffer, OAuth) are small HTTP servers whose request/response shapes come from provider docs or recorded real exchanges. Anything not yet checked against a live provider is labelled **unverified-live** in the test name or marker.
3. **Every bug becomes a regression test**, in the layer that would have caught it.
4. **Correctness-critical code gets exhaustive tests**: scheduler, state machine, publish idempotency, auto-post gate.
5. CI must be green from a clean checkout, using the same commands documented in the README.
6. **Tests are documentation a beginner can read** ([code-standard.md](code-standard.md) §10): full-sentence names, set up / do / check, one behaviour per test, explicit named cases instead of clever generators.

## 2. Pyramid and what lives where
| Layer | Scope | Tools | Speed |
|---|---|---|---|
| Unit | Pure logic: transition table, gate policy, schedule math, scoring, platform-spec validation, URL canonicalisation, prompt rendering | pytest | ms |
| Integration | ORM + services against real Postgres. Celery tasks run on a real worker with real Redis. Providers via stub servers | pytest-django, Docker services, respx or local stubs | s |
| Contract | OpenAPI snapshot (frontend contract). Adapter contract tests against recorded provider fixtures | drf-spectacular schema diff, fixtures | s |
| End-to-end | Scripted API walk: register → add credentials → link account → create plan → slot fires → post published to stub | pytest + `docker compose` | tens of s |
| Non-functional | Security, concurrency, failure injection, load | pytest, locust or k6 | minutes |

## 3. Critical areas and required tests

### 3.1 Scheduling (highest risk)
- **Named, explicit cases** (no generators): a readable list of rules, timezones and dates, including the actual spring-forward and fall-back dates for a few zones. For each case, materialisation is idempotent, produces only valid future instants, never duplicates, and handles the DST gap and repeat correctly.
- Time-travel tests with freezegun: dispatcher claims exactly the due slots, honours leases, reclaims after a simulated crash, tolerates two dispatchers racing.
- Rule edits only touch future unclaimed slots. Pausing a plan stops claims.
- Jitter stays within bounds and never moves a post after `publish_at`.

### 3.2 State machine and pipeline
- The single transition table is exhaustively tested: every allowed transition works, every other is rejected.
- Each stage is idempotent: run twice, same outcome. Kill-and-resume at every stage boundary.
- **Task registration test:** boot the real Celery app and assert every task and every Beat entry resolves to a registered task (guards V3's wrong task names).
- **Serialisation test:** every task's return value survives the configured serializer (guards V3's ORM-objects-in-result bug).
- Enqueue failure (broker down) marks the post `failed` and leaves it retryable (guards V3's stuck-`queued` bug).

### 3.3 Newsroom
- Adapters against stub feeds with real-shaped payloads, including malformed, empty and duplicate items.
- De-duplication, freshness windows, allowlist, used-article ledger.
- Quality outcomes: when nothing clears the threshold, the post is `skipped` with a reason and **nothing is published**.
- SSRF suite on the article fetcher (see 3.7).

### 3.4 Studio
- LLM client: structured-output validation, repair retries, timeouts, 429/5xx/refusal handling, token accounting.
- Poster renderer: golden-image tests for each platform size and long or short headlines. Contrast and safe-area assertions.
- **Review verdict logic** (deterministic) tested exhaustively over score and blocker combinations. Correction loop stops at 2 rounds or when the score stops improving.
- Prompt-injection fixtures: article text containing instructions must not change the verdict or leak the system prompt.

### 3.5 Publishing
- **Idempotency:** concurrent publish attempts for the same (post, account, version) produce exactly one external call.
- **Ambiguity:** stub returns a timeout after accepting the request. The record becomes `ambiguous`, reconcile resolves it, and no automatic re-post happens when status can't be confirmed.
- Token refresh before expiry, `needs_reauth` on failed refresh.
- Per-platform payload validation (length, media rules).
- **Auto-post gate:** table-driven tests over every input combination. Default is closed. Written as a plain, readable table (one row per combination of verdict, score, blockers and topic kind), so a beginner can read every rule and add a case.

### 3.6 API and contract
- Every endpoint: auth required, validation, pagination, error body shape.
- **IDOR matrix:** an auto-generated test iterates every route as user B against user A's objects and expects 404/403.
- **Secrets never leak:** API responses, logs and exception reports never contain credential values (assert on a canary secret).
- OpenAPI snapshot diff fails the build on unreviewed contract changes.
- **Cookie auth:** the refresh cookie is `HttpOnly`, `Secure` and `SameSite`. It is limited to the auth paths. `refresh` works only with the cookie and rejects a missing, expired or already-used token (rotation with reuse detection). `logout` clears it. A cross-site style request without the custom header is rejected. CORS allows credentials only for allowlisted origins.
- **Invite-only registration:** registering without a valid invite code fails, a code works once, and the `open` and `closed` modes behave as documented.
- **AI-assisted label:** appended when enabled, never appended when disabled, and the caption is shortened first so the label is never cut off at each platform's length limit.

### 3.7 Security
- SSRF: private, loopback and link-local IPs, DNS rebinding simulation, redirect to internal host, non-HTTP schemes, oversize bodies, slow responses.
- OAuth: tampered or replayed `state`, missing PKCE verifier, redirect URI mismatch.
- Throttling and quota enforcement.
- Dependency audit (`pip-audit`) and static checks (`ruff`, `bandit`) in CI.

### 3.8 Resilience and failure injection
Stub servers can be told to return 429, 500, malformed JSON, slow bodies and connection resets. Redis and the worker can be stopped mid-run. Assertions: no duplicate publishes, no lost slots, every post ends in a terminal or waiting state with a reason.

### 3.9 Load
Run locally with Docker Compose and modest container limits. Production hosting is **deferred**, so this test records the capacity of the local setup rather than promising anything about a host. Burst of about 100 simultaneous pipelines against the fake providers, which models the free-launch round-time burst. Assertions: slot-claim lag under 60s, all posts ready before `publish_at` given the 20-minute lead time, the publish queue is never starved by pipeline work, no deadlocks, bounded DB connections, and memory stays under the container limit. A second run at about 400 pipelines documents where the local setup stops being enough, and its result is reported as a capacity limit, not hidden.

### 3.10 Free-launch model (quotas, notifications, accounts, retention)
- **Quotas:** boundary tests for every limit in §17.2 (at limit passes, over limit fails with the documented problem-details body). Daily windows across timezones and DST. **Concurrency test:** many simultaneous requests racing for the last unit of a quota must never exceed it. A schedule that would exceed the daily post limit is rejected at save time. An over-quota slot becomes `skipped(quota_exceeded)` with a notification. Outage-missed slots do not consume quota. `QuotaOverride` takes effect.
- **Notifications:** every event kind creates exactly one notification, `dedupe_key` collapses repeats, unread count and read-all are correct, users only ever see their own, retention removes old rows.
- **Accounts without email:** recovery codes are single-use, stored hashed, regenerable, and throttled. Registration modes `open`, `invite` and `closed` each enforced, and invite codes are single-use. Register, login and recover throttles hold.
- **Downtime:** simulate an outage with freezegun. Slots inside `max_lateness` resume, older ones become `skipped(missed_window)`, and exactly one aggregated notification is sent per plan per outage.
- **News budgets:** an adapter stops at its daily cap and plans fall back to cached articles. Ingest fetches only topics used by active plans.
- **Retention and disk guard:** the nightly job removes images, article text, steps and notifications past their windows and leaves posts and publications. Simulated disk usage at 80% alerts and at 90% pauses ingest and generation.
- **Storage backends:** the same contract tests run against the local-volume backend and the S3-compatible backend (MinIO). Signed URLs expire as designed.

### 3.11 Readability and demo mode
- **Readability gate in CI:** the Ruff rules and `scripts/check_readability.py` run on every change. The checker has its own tests: a file over 250 lines, a module without a docstring, `async def`, `lambda`, `yield` and `*args` / `**kwargs` each make it fail, and a clean sample passes.
- **Fresh-eyes review** at the end of every phase (a reviewer with no context reads each new file once and lists what they could not follow). The list must be empty. This is a process check, recorded in the phase notes.
- **Code tour check:** a test fails if a Python file is added to an app without that app's `README.md` listing it, so the tour cannot drift from the code.
- **Demo mode end to end:** with `DEMO_MODE=true` and **no API keys**, `scripts/demo_walkthrough.py` registers a user, saves credentials, creates a plan, generates a post, approves it and publishes it to the fake publisher. Every response is labelled `demo_mode: true`.
- **Fakes match the stubs:** the same contract tests run against the demo fakes and the HTTP stub servers, so demo mode and CI cannot drift apart.

## 4. LLM and content-quality evaluation (not in CI)
Prompts and rubrics are judged on outputs, not just on code paths.
- A **golden set** of article fixtures per topic (jobs, layoffs, Linux tips, AI news) with human-labelled expectations (should be selected or rejected, factual claims, red-flag cases).
- An eval script that runs the real pipeline against the golden set with a real model key and reports selection precision, review catch rate for seeded errors, and a human-rated sample.
- Run manually when prompts or rubrics change, and whenever a human supplies real credentials. Results are reported as they are and never fabricated.

## 5. Coverage targets
Percentages are a smell, so targets are by area:
| Area | Target |
|---|---|
| Scheduler, state machine, publish idempotency, auto-post gate | 100% branch coverage, with the gate tested as an exhaustive readable table |
| Services and adapters | Every error class in the system design (§6) has a test |
| API | Every route covered by auth, IDOR and schema tests |
| Overall | Tracked, not gated. Critical-area gates enforced in CI |

## 6. Guardrails for V3's failures
| V3 failure | Test that guards it |
|---|---|
| Template crashed on a nonexistent filter | API-only now. Every endpoint exercised through the real HTTP layer |
| `NameError` on validation failure | Validation-failure test for every endpoint |
| Enqueue failure left posts stuck at `queued` | Broker-down test asserts `failed` and retryable |
| Beat entries named tasks that were never registered | Task-registration test on the real Celery app |
| Task returned ORM objects under the JSON serializer | Serialisation round-trip test per task |
| Task registered only via an import side effect | Same registration test, run in a fresh process |
| CI pointed at a nonexistent requirements file | CI runs the exact documented install and test commands |
| Production containers shipped insecure cookie settings | `manage.py check --deploy` in CI against production settings |
| Shared global Buffer token across users | Two-user isolation test: user B can never use user A's token |

## 7. Definition of done per phase
A phase is done when:
1. Its tests above pass in CI from a clean checkout.
2. `ruff`, `makemigrations --check`, `manage.py check --deploy` are green.
3. The scripted end-to-end walk for the phase's feature passes against stubs.
4. The OpenAPI snapshot is updated deliberately, with the diff reviewed.
5. Anything that talks to an external provider is marked verified-live or **unverified-live** in the docs.
6. The readability gate is green, the fresh-eyes review list is empty, and `docs/CODE-TOUR.md` and the app READMEs match the code.

## 8. Live verification checklist (needs a human)
Run once credentials exist. Record the real results, don't infer them.
- [ ] Real text key: connection test, one full draft and review.
- [ ] Real image key: one artwork, poster rendered.
- [ ] Real Buffer token: channel discovery and one real post.
- [ ] Each direct OAuth platform: link, publish, refresh, revoke.
- [ ] News: keyless sources over a day of ingest, and, only if enabled, the optional news key's real daily cap and terms.
- [ ] **Deferred until a host is chosen:** always-on behaviour, restart recovery, disk and memory limits, and measured burst capacity on that host.
