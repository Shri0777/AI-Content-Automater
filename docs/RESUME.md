# Resume notes: bullets and interview stories

Every number here was measured on 2026-11-17 (see
[CASE-STUDY.md](CASE-STUDY.md) and the Phase 9 notes in
[plan.md](../plan.md)). Re-measure before reusing one, and drop any bullet
whose number can no longer be shown.

## Resume bullets

- **Designed and built a scheduled AI content platform** (Django, Celery,
  PostgreSQL, Redis) that finds news, writes captions and poster images with
  any user-supplied AI model, reviews and corrects them with an AI reviewer
  whose verdict is decided by code, and publishes through Buffer, X,
  LinkedIn and Facebook.
- **Rebuilt a failing prototype into a verified system:** diagnosed why 428
  passing tests missed production failures (they mocked the real paths),
  then rebuilt it with real-wiring tests: 475 tests against a real database
  and HTTP stub servers, 92% branch coverage (96% on critical modules),
  enforced in CI.
- **Engineered a crash-safe, database-backed scheduler:** slots claimed
  with `SKIP LOCKED` and leases, tested over 9 named daylight-saving cases
  and with three dispatchers racing; a 400-post burst was ready in 56 s on
  a laptop with no failures.
- **Made publishing idempotent:** unique keys per post and account, an
  "unconfirmed" state for requests that got no answer, and two-worker race
  tests that found and fixed a bug marking live posts as failed.
- **Hardened security:** SSRF and DNS-rebinding protection checked at
  connection time, OAuth with single-use state and PKCE, encrypted keys, an
  automated test that tries every API address as another user, and a review
  that closed an account-takeover path through recovery codes.
- **Enforced a beginner-readable code standard in CI** (function and file
  length, complexity, argument counts, banned constructs) across 239 files.

## Interview stories (each backed by code and tests)

1. **From "passing" to working.** V3's tests mocked the paths that broke.
   V4 starts from a walking skeleton and tests real wiring.
   → `docs/CASE-STUDY.md`, `tests/stub_server.py`.
2. **Never post twice.** Idempotency keys, the `ambiguous` state, and why a
   missing post beats a duplicate. The race test that found a post shown as
   failed while live. → `publishing/services.py`,
   `publishing/tests/test_unconfirmed_posts.py`.
3. **Scheduling that survives crashes and daylight saving.** Leases,
   `SKIP LOCKED`, the 50-per-minute cap found by the load test.
   → `planning/dispatcher.py`, `planning/tests/test_schedule.py`.
4. **AI you can trust.** The model rates and reviews; fixed rules decide.
   Prompt-injection defences, a closed-by-default auto-post gate tested as a
   table. → `studio/verdicts.py`, `studio/guards.py`, `publishing/gate.py`.
5. **Being a good citizen on the web.** Daily request budgets, "only if
   changed" feeds, and reading article pages only where robots.txt allows AI
   readers. → `newsroom/fetching.py`.
6. **Readable by design.** The standard and the CI checker.
   → `design/code-standard.md`, `scripts/check_readability.py`.

## What not to claim

- Real users, traffic, uptime or savings: there are none yet.
- Working live with LinkedIn, X, Meta or Buffer: every adapter is verified
  against stub servers that follow each platform's documentation, not
  against the live platforms (only Buffer's refusal of a bad key was seen
  live).
- That demo output is real AI output.
- Load numbers as real-AI performance: they were measured with fake
  providers that answer in milliseconds.
