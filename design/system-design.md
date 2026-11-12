# AI Content Automator: Backend System Design (V4)

Status: **Draft for review** · Scope: backend only (REST API + workers). The frontend is planned separately and consumes the OpenAPI schema.
Companion docs: [decisions.md](decisions.md) (ADRs), [test-strategy.md](test-strategy.md), [../plan.md](../plan.md) (build plan).

---

## 1. Purpose and scope
Users connect their own AI keys and social accounts, describe what they want posted, and set a schedule. The system finds high-quality news, writes posters (caption plus AI image), reviews and corrects them, then either posts automatically or waits for human approval.

**In scope:** accounts, credentials, social linking, plans and schedules, news ingestion and curation, generation pipeline, review and correction, approval, publishing, notifications, audit.
**Out of scope (for now):** frontend, billing, team workspaces, analytics dashboards, comment/DM handling.

## 2. Requirements

### 2.1 Functional (user's requirements 1–10)
| ID | Requirement |
|---|---|
| FR1 | Separate user-supplied API keys for **text** and **image** generation (and an optional **news** key). |
| FR2 | Any text model (via LiteLLM model string and optional base URL). Image models via adapters. |
| FR3 | Link Buffer or social accounts directly with a simple flow. |
| FR4 | Schedule: number of posts, times, days of the week, in the user's timezone. |
| FR5 | Connected news sources, without forcing every user to set up a news API. |
| FR6 | Per-plan user requirements (free text and topics) drive news search. |
| FR7 | Text model writes the image prompt, and the image model renders it. |
| FR8 | Generated posts are verified by AI review and corrected when needed. |
| FR9 | Per plan: auto-post after successful AI review, or manual approval. |
| FR10 | Content is high quality: jobs, layoffs, Linux tips, AI news, each with appropriate sourcing. |

### 2.2 Non-functional (targets, to be validated)
| Area | Target |
|---|---|
| Correctness | **Zero duplicate publishes.** No lost slots. Every post has a terminal or waiting state and a reason. |
| Timeliness | 99% of approved posts publish within ±2 minutes of `publish_at`. Generation starts `lead_time` (default 20 min) earlier so the post is ready on time. |
| Availability | A provider outage (LLM, image, news, Buffer) degrades only the affected posts, never the whole system. |
| Security | User secrets encrypted at rest and never returned by the API. SSRF-safe outbound fetching. Strict owner scoping. |
| Cost | **Free to users at launch.** Users bring their own AI keys. The operator will run on one small always-on host with free or self-hosted services (hosting choice deferred), keyless news by default, and per-user quotas that protect compute, storage and the shared news budget (§17). |
| Observability | Any post's full history (every stage, model, token count, error) is reconstructable. |
| Readability (top requirement) | A beginner can read every file in one sitting. Simple syntax only, no feature compromised, enforced by CI ([code-standard.md](code-standard.md)). |
| Showcase | Anyone can run the full pipeline with no API keys through demo mode (§18, [resume-showcase.md](resume-showcase.md)). |
| Evolvability | New news source, image model or social platform = one adapter, no pipeline change. |

### 2.3 Constraints and assumptions
- Django/DRF/Postgres/Celery/Redis (approved stack). Small team; operational simplicity beats cleverness.
- **Beginner-readable code (top requirement):** the whole codebase uses the "Beginner Subset" of Python and a fixed, predictable layout. Complexity lives in small named functions and plain data, never in clever syntax ([code-standard.md](code-standard.md)).
- **Resume showcase (goal):** the project must be runnable by a newcomer with no keys, and every claim must be measured ([resume-showcase.md](resume-showcase.md)).
- **Deployment is deferred.** Local Docker Compose only for now. §17.6 to §17.10 are kept as the checklist for when hosting is chosen.
- **Free launch (decided):** no billing, no payment code, **in-app notifications only** (no email). Per-user free limits are the only limiter (§17).
- **Assumed scale (to validate):** design target 1,000 active users averaging 3 posts per day (about 3,000 posts per day). **Free-launch target: about 200 users on one host** (§17.6). The numbers in §3 use the design target.
- Providers' real API behaviour is not assumed. Every adapter is tested against recorded or documented shapes, and flagged **unverified-live** until a human runs it with real credentials.

## 3. Load estimation (assumption-based)
- **Posts:** 3,000 per day, roughly 0.035 per second on average.
- **LLM calls per post:** about 1 batch relevance scoring, 1 draft, 1 image prompt, 1 review, plus up to 2 correction rounds (2 calls each). That is **4 calls typically, 8 worst case**, so 12k–24k calls per day. About 0.15–0.3 per second on average.
- **Images:** 3,000 per day, around 1–3 MB after poster rendering, so about 3–9 GB per day of new objects before lifecycle rules. Retention policy matters (see §13).
- **Burst is the real constraint, not the average.** Users pick round times ("09:00", "18:00"). If 40% of users share one slot, about 400 pipelines start in the same minute. Mitigations:
  - **Jitter:** `generate_at = publish_at - lead_time ± random(0..5 min)`, so generation load smears out.
  - **Per-credential concurrency limit** (default 2): each user's key has its own provider rate limit, so this protects their key and the provider.
  - **Separate queues:** `pipeline`, `publish`, `ingest`, `maintenance`. Publish jobs are never starved behind LLM calls.
- **News API:** shared key, so fetch once per topic query and cache, not once per user (see §7).

## 4. Architecture overview
See the diagrams (architecture, pipeline sequence, post lifecycle, data model) linked from [../plan.md](../plan.md).

**Modular monolith, multiple process types, one codebase:**
| Process | Role |
|---|---|
| `web` (gunicorn) | REST API, OAuth callbacks, health. Stateless. |
| `worker-pipeline` | Research, draft, image, review stages. Concurrency tuned to provider limits. |
| `worker-publish` | Publishing, reconcile, token refresh. Small and always available. |
| `worker-ingest` | News ingestion and cleanup. |
| `beat` | Triggers periodic tasks (dispatch, materialise, ingest, reconcile, refresh, cleanup). Safe to run more than once, because every trigger claims work through the DB. |
| Postgres | System of record. |
| Redis | Celery broker and short-lived caches/locks only. **Nothing durable lives only in Redis.** |
| Object storage (S3-compatible) | Poster images. Private bucket with time-limited signed URLs. |

External: LLM providers (via LiteLLM), image providers, news sources, social platforms (Buffer and direct OAuth). There is no email provider: notifications are in-app only (§17.4).

## 5. Scheduling subsystem (the heart of correctness)

### 5.1 Model
- `ScheduleRule` (local days and times plus timezone) is materialised into `PostSlot` rows on a rolling horizon (default 14 days) by an hourly task.
- `UNIQUE(plan, publish_at)` makes materialisation idempotent. Re-running it never duplicates slots.
- Rules are stored in **local time + IANA timezone**; conversion to UTC happens at materialisation. Spring-forward gaps shift to the next valid minute. Fall-back repeats use the first occurrence. A rule edit regenerates only future, unclaimed slots.

### 5.2 Dispatch
A once-a-minute dispatcher claims due slots with `SELECT ... FOR UPDATE SKIP LOCKED`, creates the `Post` in `scheduled → researching`, and enqueues the first stage. A slot is "due" when `generate_at <= now`. A **lease** (`claimed_until`) lets a crashed worker's claim expire so another dispatcher can reclaim it. Safe with multiple beats, multiple web nodes and worker restarts.

### 5.3 Publish timing
Generation and publishing are separate clocks. The post is **ready** before `publish_at`. Auto mode publishes at `publish_at`. Manual mode needs approval before `publish_at`. If approval is late, the plan's `on_missed_approval` policy applies: `expire` (default, since stale news loses value) or `hold`. A slot that cannot start within `max_lateness` of `publish_at` (for example after downtime) is skipped rather than posted stale (§17.7).

## 6. Generation pipeline as a persisted state machine

```
scheduled → researching → drafting → imaging → reviewing ⇄ correcting
          → awaiting_approval | approved → publishing → published
terminal side exits: skipped (no good content), rejected, failed, expired
```

- **One Celery task per stage**, each **idempotent**: it reads its inputs from the DB, writes its outputs, then advances the state and enqueues the next stage. A crash mid-stage re-runs that stage only.
- All task arguments and return values are IDs and plain dicts (never ORM objects).
- Every stage writes a `GenerationStep` (model, prompt version, tokens, cost, duration, error). This is the audit trail and the debugging tool.
- The transition table is **one data structure** used by the model, the API and the tests.
- **Error classes:**
  | Class | Examples | Action |
  |---|---|---|
  | Retryable | 429, 5xx, timeout, connection reset | Exponential backoff with jitter, bounded attempts |
  | Credential | 401/403 from a user's key | Mark credential `invalid`, pause the plan, notify the user. Do not retry. |
  | Content | Provider refusal or policy block | One regeneration with a different angle, then `skipped` with reason |
  | Quality | No article clears the threshold | Widen the search once, then `skipped` with reason (**never post filler**) |
  | Permanent | Malformed output after retries | `failed` with reason, retryable by the user via API |
- **Circuit breaker** per credential: repeated failures stop new work for that credential for a cool-down.

## 7. Newsroom: getting high-quality content

### 7.1 Two tiers (shared ingest, per-plan selection)
1. **Shared ingest (operator-funded, no LLM):** `ingest` tasks pull each active topic preset's sources (keyless APIs, curated RSS, and an **optional** operator news key that is off by default) on an interval. Ingest is demand-driven (only topics used by an active plan) and budgeted per source (§17.8). Items are normalised, de-duplicated and stored once in `Article`. All users benefit from one fetch, and the shared news key's quota scales with **topics, not users**.
2. **Per-plan selection (user-funded, LLM):** at research time the plan's topic selects a shortlist from `Article`, using cheap heuristics first. The user's **text model** then scores the top K (default 5) in one structured call. Tokens are bounded by K.

Users may add their own news key (`kind=news`) for extra sources and limits. It feeds the same ingest path, scoped to that user.

### 7.2 Quality gates (in order)
1. **Source policy:** per-topic allowlist/blocklist and a source tier (primary/reputable/aggregator).
2. **Freshness window:** per topic (for example layoffs 48h, AI news 72h, evergreen exempt).
3. **De-duplication:** canonical URL plus normalised-title similarity, so the same story from five outlets is one candidate.
4. **Extractability:** full text fetched (SSRF-safe) and cleaned. Paywalled or empty bodies are dropped.
5. **Heuristic score:** tier, recency, text length, entity presence.
6. **LLM scoring (structured JSON):** relevance to the plan's requirements, credibility, novelty, and "is the claim verifiable from the text".
7. **Used-article ledger:** `ArticleUse(plan, article)` so a plan never repeats a story.

### 7.3 Evergreen topics (for example "Linux tips")
Not news. Their `Topic.kind = evergreen` pulls from a curated pool (project documentation, reputable maintainers' write-ups) instead of a freshness-filtered feed. The review stage applies stricter checks for anything containing commands or code, because a wrong command harms real users. The auto-post gate (§8.4) is stricter for this kind.

### 7.4 Copyright and attribution
Store extracted text only as working data with a TTL (default 30 days). Posts summarise and attribute (source name and link on every post) instead of reproducing. The reviewer flags near-verbatim copying.

### 7.5 Topic presets
Presets are **data**, not code: source lists, freshness windows, scoring hints and image style for "Job hiring", "Layoffs", "Linux tips", "AI news", editable by the operator without a release. Curating the actual source lists is a content task done during the newsroom phase.

## 8. Studio: drafting, imaging, review, correction

### 8.1 LLM layer
A single `LLMClient` wraps LiteLLM. It handles per-credential timeouts, structured output validated by Pydantic with bounded repair retries, token/cost accounting, and capability flags per model (structured output, vision). Prompts are versioned templates in the repo, and the template version is stored on each `GenerationStep`.

### 8.2 Image layer
`ImageAdapter.generate(prompt, size, seed?) -> bytes` with adapters for OpenAI-compatible endpoints, NVIDIA FLUX, and fal/Replicate. Per-platform size comes from `platform_specs` data. The text model writes the image prompt (FR7), constrained to "no readable text in the image".

### 8.3 Poster rendering
The AI image is **artwork only**. A Pillow renderer overlays the headline and source line using bundled fonts and a safe-area/contrast-aware template. Results are crisp and always spelled correctly, and layouts stay on-brand per platform size.

### 8.4 Review and correction
- **Rubric (structured):** factual grounding against the article text, relevance to requirements, clarity, tone, safety and legal sensitivity (layoffs and hiring name real companies and people), caption/image coherence, platform fit.
- **Output:** scores, a list of issues with severity and `fix_instruction`, and a **verdict computed deterministically** from scores and blockers (`pass`, `revise`, `reject`), not decided by the model's say-so.
- **Correction loop:** up to 2 rounds. Stop early if the score does not improve. After the limit, the post goes to manual review regardless of mode.
- **Vision check** only if the configured text model declares vision capability. Otherwise it is text-only (prompt plus caption).
- **Untrusted input:** article text is passed as delimited data. The reviewer's instructions say to ignore any instructions inside it.

### 8.5 Auto-post gate (policy function, human-authored)
`may_autopublish(post, plan) -> bool` is the single place that decides whether a reviewed post may skip human approval. Inputs: verdict, score, blocker issues, topic kind and sensitivity, plan threshold. **Default is closed:** anything not a clean `pass` goes to manual approval. This encodes the owner's editorial risk tolerance and is deliberately small and exhaustively tested.

## 9. Publishing and social linking

### 9.1 Publisher interface
```
link_start(user, platform) -> redirect_url
link_callback(params) -> SocialAccount
publish(account, payload) -> PublishResult
check_status(account, external_id) -> Status
refresh(account) -> account
```
Adapters: **Buffer** (paste a token; channels auto-discovered), then **LinkedIn**, **X**, **Meta (Facebook Pages, Instagram)** via OAuth. Platform limits (length, media specs) live in `platform_specs` data.

### 9.2 Link flow (direct OAuth)
1. Frontend calls `POST /social/link/{platform}/start/` and receives the authorisation URL.
2. The user consents at the platform. The platform redirects to the backend callback.
3. Backend validates the signed `state` (and PKCE where supported), exchanges the code, stores encrypted tokens, discovers the account/page, and redirects back to the frontend with a result code.

Honest constraints: each platform needs an operator-registered developer app, and some publishing scopes need platform app review. Buffer is the fallback that works without review.

### 9.3 Publish correctness
- `Publication.idempotency_key = hash(post, account, version)`. Publishing is a claim, then a call, then a record.
- **Ambiguous outcomes** (timeout after request sent) are stored as `ambiguous` and resolved by a reconcile task calling `check_status` with the account's own token. If a platform cannot confirm status, the system **does not auto-retry** and escalates to the user. A duplicate post is worse than a missing one.
- **Token refresh** runs ahead of expiry. A failed refresh sets the account `needs_reauth` and notifies the user.
- Images are handed to publishers as signed URLs (URL-based adapters) or uploaded as bytes (byte-based adapters), whichever the platform requires.
- **AI-assisted label:** each plan has `ai_label_enabled` (default on) and `ai_label_text`. The caption is shortened to fit the platform's length limit **before** the label is appended, so the label is never truncated. When the label is off, nothing is added. Whether a given platform requires or encourages such a label is not assumed here. It is checked against that platform's current rules when its adapter is built.

## 10. Data model
Key tables are listed in [../plan.md](../plan.md#5-data-model-key-tables) and drawn in the ER diagram. Design rules:
- Immutable `PostVersion` rows. An edit or correction creates a new version, never mutates.
- Secrets stored in `BinaryField` as MultiFernet ciphertext; API serializers declare them **write-only**.
- Soft-delete only where history matters (posts, publications). Hard-delete credentials and tokens on user request.
- Indexes for the hot paths: `PostSlot(status, generate_at)`, `Post(plan, status)`, `Article(url_hash)`, `Publication(idempotency_key)` unique.

## 11. API design
- REST under `/api/v1/`, OpenAPI 3 generated by drf-spectacular, with a **snapshot test** so the frontend contract cannot change silently.
- **Auth:** email login, short-lived JWT access plus rotating refresh. The refresh token lives in an httpOnly cookie and the access token in frontend memory (ADR-009).
- **Conventions:** cursor pagination, filter and ordering on list endpoints, consistent problem-details error body, `Idempotency-Key` header on mutating POSTs (approve, generate-now), `202 Accepted` plus a pollable resource for long operations.
- **Live status:** polling in v1 (post status plus `GenerationStep` list). Server-sent events or webhooks can be added later without model changes.
- **Rate limiting:** DRF throttles per user and per endpoint class. Per-user daily quotas for generations and posts.

## 12. Security

### Threat model (condensed)
| Threat | Mitigation |
|---|---|
| Stolen or leaked user API keys | Fernet/MultiFernet at rest, key from env or secret manager with rotation, write-only fields, redacted logs, no keys in error reports |
| SSRF via user `base_url` or article URLs | Resolve then validate, block private, loopback and link-local ranges, re-validate on every redirect, size and time limits, no non-HTTP(S) schemes |
| Prompt injection from scraped news | Delimited untrusted content, instruction-ignoring system prompt, review stage, output schema validation, no tool access from the LLM |
| OAuth CSRF and code interception | Signed single-use `state`, PKCE, exact redirect-URI allowlist |
| IDOR | Every view filters by the logged-in owner, plus an automated test that walks all routes as a second user |
| Abuse (spam, cost) | Free quotas (§17.2), throttles, registration modes (`open`, `invite`, `closed`), plan pause on repeated credential failure, per-account post-rate caps |
| Account takeover | Password hashing, throttled login, refresh rotation and revocation, one-time recovery codes (no email in free mode, §17.5) |
| Harmful or defamatory output | Review rubric weights legal sensitivity, stricter auto-post gate for sensitive topics, AI-content disclosure option per platform policy |

Production settings enforced: HTTPS, secure cookies, strict `ALLOWED_HOSTS` and CORS allowlist.

## 13. Reliability, failure modes and scale

| Failure | Behaviour |
|---|---|
| Redis down | API still serves reads. Enqueue failures mark the post `failed` (retryable). Slots stay unclaimed in the DB and are picked up when Redis returns. |
| Worker crash mid-stage | Lease expires, stage re-runs idempotently. |
| LLM or image outage | Retries with backoff, then the post fails with reason. The credential's circuit breaker protects the user's key. |
| News API quota exhausted | Ingest degrades to keyless sources. Plans fall back to the cache. Operator alerted. |
| Buffer or platform outage | Publish retries. Ambiguous outcomes are reconciled. Never auto-duplicate. |
| Token expired or revoked | `needs_reauth`, notification, plan keeps generating and holds posts for approval. |
| Clock or DST edge | Rules in local time, UTC slots, tests over named daylight-saving dates. |
| DB failover | Idempotent tasks and DB-held state mean in-flight work resumes. |

**SLOs:** slot-claim lag under 60s (p99), publish within ±2 min of `publish_at` (99%), zero duplicate publications.
**Scaling path:** add worker replicas per queue first. Then read replicas for list endpoints. Then partition `GenerationStep` and `Article` by time. Poster images expire after a retention period (default 30 days, or on account deletion; see §17.9).

## 14. Observability
- Structured JSON logs carrying `request_id`, `post_id`, `stage`, `user_id`.
- Metrics: stage latency and failure rate per provider, queue depth per queue, slot lag, publish success rate, skip rate and reasons, cost per post.
- Alerts: slot lag, publish failure spike, ingest stalled, queue depth, credential-invalid rate.
- Admin views for operators. A cost ledger from `GenerationStep` gives per-user usage.

## 15. Trade-offs and what to revisit
| Decision | Gain | Cost | Revisit when |
|---|---|---|---|
| Modular monolith | One deploy, simple transactions | Shared fate, one language | Pipeline load needs independent scaling beyond queue-per-process |
| DB as scheduler source of truth, Celery as executor | Crash-safe, inspectable, restart-proof | More DB writes than in-memory schedulers | Slot volume exceeds a few million per day |
| BYO keys for AI | No inference cost to operator, any model | Users must obtain keys, quality varies by model | Add an operator-funded tier with billing |
| Hybrid shared news ingest | Cheap, scales with topics not users | Shared source list needs curation | Per-user source customisation demand |
| Polling for status | Trivial and robust | Slight latency and extra requests | Frontend wants live updates |
| Pillow poster overlay | Always-correct text | Less "creative" layouts than full AI posters | Users ask for richer templates |

## 16. Open questions
**Decided:** notifications are in-app only. The product launches free with per-user limits (§17).

Also decided:
1. **Auth tokens:** refresh token in an httpOnly cookie, access token in frontend memory (ADR-009).
2. **Registration:** `invite`-only at launch (§17.5). `open` and `closed` remain settings.
3. **AI-assisted label:** optional per plan, default on (§9.3).
4. **Ownership:** single owner per plan, credential and social account. No shared workspaces.
5. **Hosting target:** deferred by decision. Revisit when the project is ready to deploy (§17.10).

Defaults applied unless the owner objects: the optional paid news key stays off (keyless sources only), and Python and Django versions are the newest stable releases at setup time.

---

## 17. Free operating model (decided: launch free, in-app notifications only)

### 17.1 Principles
- **No billing, no paywalls, no payment code in v1.** Quotas are the only limiter. They are configurable data (`QuotaPolicy`, default tier `free`), so tiers can be added later without a redesign.
- **Users pay for their own AI** (bring-your-own keys). Quotas therefore protect only the operator's resources: compute (pipeline runs), storage (posters), the shared news budget, and outbound posting volume (spam).
- **Operator cost target:** one small always-on host plus free or self-hosted services. Every choice below keeps the footprint small.

### 17.2 Free limits per user (proposed defaults, editable without a release)
| Resource | Free limit | Why |
|---|---|---|
| Active content plans | 3 | Bounds scheduling and ingest breadth |
| Topics per plan | 6 | Bounds news selection per run |
| Linked social accounts | 5 | Bounds publishing fan-out |
| Posts generated per day (all plans) | 6 | Main compute and storage driver. A post counts once it reaches `drafting`. |
| Posts generated per plan per day | 4 | Stops one plan consuming the whole allowance |
| Schedule horizon | 14 days ahead | Bounds materialised slots |
| Manual "generate now" runs | 5 per day | |
| Regenerations per post | 3 | Stops costly regeneration loops |
| Automatic correction rounds | 2 (system rule) | Already designed (§8.4) |
| Credentials | 1 active per kind (text, image, news) | |
| News preview requests | 30 per day | Protects the shared ingest cache |
| API requests | 120 per minute per user. Login, register and recover: 10 per minute per IP | |
| Poster storage | 250 MB per user (posters stored as optimised WebP/JPEG, target 500 KB or less, so roughly 500 posters) | |
| Poster retention | 30 days, then the image expires (post text and history stay) | |

These are starting points to validate against the real host, not promises.

### 17.3 Enforcement
- A `QuotaService` in `core` exposes `check(user, resource)` and `consume(user, resource)`. Daily windows are computed in the **user's timezone** and stored as `QuotaUsage(user, resource, window_start, used)`. Static limits (plans, accounts) use live counts.
- **Atomic consume:** a conditional update (`UPDATE ... SET used = used + 1 WHERE used < limit`), so two concurrent requests can never both exceed a limit.
- **API behaviour:** `429` for rate limits, `403` for quotas, both with a problem-details body containing `code=quota_exceeded`, `resource`, `limit`, `used` and `resets_at`.
- **`GET /me/usage/`** returns every limit and current usage so the frontend can show meters.
- **Up-front validation:** a schedule that would exceed the daily post limit is rejected when saved ("this schedule creates 8 posts per day, your limit is 6"), not discovered at 09:00.
- **At run time:** a slot that fires over quota becomes `skipped` with `skip_reason=quota_exceeded` plus an in-app notification. Nothing is silently dropped. Slots lost to an outage do not count toward quota.
- **Operator overrides:** `QuotaOverride(user, resource, limit)` managed in the admin.

### 17.4 In-app notifications (the only channel)
- `Notification` rows: user, kind, title, body, links to the related post, plan or account, `created_at`, `read_at`, `dedupe_key`.
- **Kinds:** `post_awaiting_approval`, `post_published`, `post_failed`, `post_skipped` (with reason), `post_expired`, `account_needs_reauth`, `credential_invalid`, `quota_reached`, `plan_paused`, `outage_missed_slots`.
- **API:** `GET /notifications/` (cursor, `?unread=true`), `GET /notifications/unread-count/`, `POST /notifications/{id}/read/`, `POST /notifications/read-all/`, and `GET /me/summary/` (unread count, posts awaiting approval, accounts needing attention) so the frontend can poll one cheap endpoint every 30 to 60 seconds.
- **Noise control:** `dedupe_key` collapses repeats (for example one `credential_invalid` until it is fixed, one `outage_missed_slots` per plan per outage). Notifications are kept for 60 days.
- **Consequence:** a manual-approval user only learns about pending posts when they open the app. Mitigations: the `on_missed_approval` policy (default `expire`) and the awaiting-approval count in `/me/summary/`. A `Notifier` interface writes in-app notifications now, so push or email channels can be added later behind the same table without touching the pipeline.

### 17.5 Accounts without email
There is no email provider, so there is no email verification and no emailed password reset.
- **Recovery codes:** 8 one-time codes are generated at registration, shown once, and stored hashed. `POST /auth/recover/` accepts a code to reset the password. Codes can be regenerated while logged in.
- **Registration modes:** `REGISTRATION_MODE = open | invite | closed`. `invite` uses single-use `InviteCode`s so the operator controls growth and abuse while the product is free. Recommended launch default is `invite` until quotas and throttles are proven, then `open`.
- The frontend may add a CAPTCHA. The backend exposes a verification-token hook (provider to be chosen and its API verified at implementation).
- Register, login and recover are throttled per IP and per identifier.

### 17.6 Resource budget and topology (deferred with deployment)
*Kept as reference for when a host is chosen. Locally we run one worker with Docker Compose. The threaded pool below is a single line of Celery configuration, not new code.*

**Target host (assumption to measure):** 1 to 2 vCPU, 2 GB RAM, always on.
| Process | Free-launch setting |
|---|---|
| web | gunicorn, 2 workers |
| worker-publish | Concurrency 1, own queue, so publishing is never starved |
| worker-main | Threads or gevent pool, concurrency about 16, queues `pipeline`, `ingest`, `maintenance`. Pipelines are network-bound (waiting on LLM and image APIs), so a threaded pool gives high I/O concurrency for little memory. Poster rendering is short CPU work. |
| beat | One small process |
| postgres | Small, `shared_buffers` about 256 MB |
| redis | `maxmemory` about 128 MB, broker keys never evicted |
| storage | Local volume by default, S3-compatible optional (ADR-011) |

A rough memory budget is Postgres 300 to 400 MB, Redis up to 128 MB, web 2 x about 100 MB, workers 2 x about 200 MB, plus OS headroom. These are estimates to measure, not measurements.

**Burst reality check.** With about 90 s per pipeline and concurrency 16, the host clears roughly 10 pipelines per minute. A round-time burst of about 100 pipelines therefore takes about 10 minutes, which fits inside the 20-minute `lead_time` plus jitter. A burst of several hundred does not, and would need a bigger host or more workers. The free-launch target of about 200 users, capped at 6 posts per day each, keeps typical bursts under that line. The ingest worker is a separate queue, not a separate process, in free mode, so it can be split out later without code changes.

### 17.7 Tolerating downtime
Always-on hosts still restart, and cheap ones can go down.
- Each plan has `max_lateness` (default 30 minutes). On recovery the dispatcher resumes slots whose `publish_at + max_lateness` has not passed, and skips older ones with `skip_reason=missed_window` instead of posting stale news.
- The user gets one aggregated `outage_missed_slots` notification per plan per outage. Missed slots do not count toward quota.
- Because slot state lives in Postgres and stage tasks are idempotent (§5, §6), a restart loses no work.

### 17.8 News on a free budget
- **Default sources are keyless:** Hacker News search, Google News RSS and curated RSS lists. A paid news key is optional and off by default.
- **`SourceBudget` per adapter:** a daily request cap, tracked in the database. Ingest stops an adapter at its cap and plans fall back to cached articles. Free-tier news APIs commonly have small daily caps and may restrict commercial use, attribution or article freshness. **Verify each provider's current terms before enabling one.** Nothing here assumes a specific provider's limits.
- **Good citizenship:** honour `robots.txt` and site terms, send an identifying User-Agent, rate limit per domain, use `ETag` and `Last-Modified`.
- **Demand-driven ingest:** only topics used by at least one active plan are fetched.

### 17.9 Retention (keeps the free host's disk and database small)
| Data | Retention |
|---|---|
| Poster images | 30 days, then `image_expired` (post text and history are kept) |
| Article extracted text | 14 days (metadata 90 days) |
| `GenerationStep` | 90 days, then daily aggregates are kept |
| Notifications | 60 days |
| Posts, versions, publications | Kept as the user's history unless the user deletes them |

A nightly maintenance task enforces this. A **disk guard** alerts at 80% disk use and pauses ingest and generation at 90%, failing safe before the host runs out of space.

### 17.10 Hosting risk (deferred by decision)
*Deployment is deferred. This section is the checklist for when hosting is chosen.*

Free PaaS tiers typically sleep idle services or limit background workers. That is incompatible with a scheduler that must fire at exact times. The design therefore requires an **always-on host**. Realistic options are an always-free cloud VM (availability and policy vary, so verify), a home server or Raspberry Pi with a tunnel, or the cheapest small VPS (a few dollars a month) as the practical floor. Everything runs in Docker Compose with multi-arch images (ARM-friendly), so the choice stays open. I will not claim a zero-cost option works until you pick a target and its limits are verified.

---

## 18. Beginner-readable by design, and demo mode

### 18.1 How the architecture stays readable
The architecture is the same, but each part is written in the Beginner Subset ([code-standard.md](code-standard.md)). The consequences for the design:
- **One-way flow:** views call services, services call models and adapters, tasks call services. A beginner can follow any request by reading downward through four small files.
- **Predictable app layout:** every app has the same file names, so there is nothing to hunt for.
- **Plain data over frameworks:** the status table is a dict, the schedule is rows, the quota limits are rows, the topic presets are data.
- **Libraries are wrapped once:** LiteLLM, Pillow, trafilatura and cryptography each live in one file behind one obviously named function.
- **Small stages:** each pipeline stage is a service function of 20 lines or fewer, wrapped by a Celery task of 10 lines or fewer.
- **Four isolated exceptions** to the standard (dispatcher `skip_locked`, atomic quota update, encryption helpers, and the post tasks' catch-and-re-raise so a crash marks the post `failed`), each commented with why it exists.

### 18.2 Demo mode (ADR-014)
`DEMO_MODE=true` replaces every external provider with a built-in fake so the full pipeline runs with **no API keys and no network**:
| Real provider | Demo fake |
|---|---|
| Text model (LiteLLM) | Fake text model returning deterministic, template-based captions, image prompts and review JSON |
| Image model | Pillow-generated artwork (gradients and shapes) so the poster renderer still runs for real |
| News sources | Canned articles for each preset topic (jobs, layoffs, Linux tips, AI news) |
| Buffer and social platforms | A fake publisher that records the post in the database |

- The fakes implement the **same base classes** as the real adapters, so the pipeline code is identical in both modes.
- Responses and stored records carry `demo_mode: true`, and the README states that demo content is canned.
- The same fakes serve the test suite, so there is one implementation to maintain.
- A seeded demo user and plan make the first request show something real.
