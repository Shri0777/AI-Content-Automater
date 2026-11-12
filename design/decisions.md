# Architecture Decision Records (V4 backend)

Format: Context, Decision, Options, Trade-offs, Consequences. All entries are **Proposed** until reviewed.
Related: [system-design.md](system-design.md).

---

## ADR-001: Modular monolith on Django + DRF
**Status:** Proposed · **Deciders:** project owner

**Context.** Small team, backend-only API for a separately built frontend, heavy async work (pipelines, publishing), strong need for auth, admin and an ORM. The previous app was Django too, so the team knows it.

**Decision.** One Django codebase organised as apps (`accounts`, `credentials`, `social`, `planning`, `newsroom`, `studio`, `publishing`, `core`), deployed as several process types (web, workers, beat). API via Django REST Framework with drf-spectacular.

| Option | Complexity | Team familiarity | Fit |
|---|---|---|---|
| **A. Django + DRF monolith** | Low | High | Auth, admin, migrations and ORM included |
| B. FastAPI + SQLAlchemy | Medium | Medium | Lighter and async-native, but auth, admin and migrations are assembled by hand |
| C. Microservices | High | Low | Premature. No independent scaling need yet |

**Trade-offs.** Gives up native async request handling, but the work that needs concurrency runs in Celery, not in requests.
**Consequences.** Easier: transactions, one deploy, admin for operators. Harder: independent scaling. Revisit if pipeline load must scale separately beyond queue-per-process.

---

## ADR-002: Postgres is the scheduler's source of truth; Celery only executes
**Context.** The old app's Beat entries referenced task names that were never registered, and nothing proved they ran. Users need exact scheduling (days, times, timezones) and **no duplicate or lost posts**.

**Decision.** Rules materialise into `PostSlot` rows with `UNIQUE(plan, publish_at)`. A once-a-minute dispatcher claims due slots with `FOR UPDATE SKIP LOCKED` plus a lease, and enqueues stage tasks. The pipeline is a persisted state machine with one idempotent task per stage.

| Option | Crash safety | Inspectability | Complexity |
|---|---|---|---|
| **A. DB slots + claim/lease dispatcher** | High | High (rows) | Medium |
| B. `django-celery-beat` per-user periodic tasks | Medium | Medium | Medium, but one periodic task per schedule does not scale and DST handling is awkward |
| C. Temporal/Airflow-class orchestrator | High | High | High (new infrastructure) |

**Consequences.** Easier: restarts, multi-beat safety, debugging ("show me slot X"). Harder: more DB writes and a dispatcher to maintain. Revisit at millions of slots per day.

---

## ADR-003: LiteLLM for text; adapter interface for images
**Context.** "Accept any AI model" (FR2). Text providers largely converge on chat-completion shapes. Image APIs do not.

**Decision.** Text: LiteLLM (`model` string, optional `base_url`, user key) behind our own `LLMClient` (timeouts, Pydantic-validated structured output, cost accounting, capability flags). Images: `ImageAdapter` interface with OpenAI-compatible, NVIDIA FLUX and fal/Replicate adapters.

**Trade-offs.** One more dependency and its release cadence. We still pin and wrap it so swapping it out is local. We make no claim that every image model works without an adapter.
**Consequences.** New text model = config. New image model = a small adapter plus a contract test.

---

## ADR-004: Social publishing via a `Publisher` interface; Buffer first, direct OAuth next
**Context.** Users want simple linking. Direct platform APIs need operator-registered apps and sometimes app review, and X write access is tier-limited. Buffer works with a token and no review.

**Decision.** A `Publisher` interface (`link_start`, `link_callback`, `publish`, `check_status`, `refresh`). Build order: Buffer, LinkedIn, X, Meta (Facebook Pages, Instagram). The product degrades gracefully: anything that can't be linked directly can be linked through Buffer.

| Option | Time to value | Dependency risk |
|---|---|---|
| **A. Interface with Buffer first, then OAuth adapters** | Fast | Spread across adapters |
| B. Direct OAuth only | Slow (app reviews) | High |
| C. Third-party unified API only | Fast | Vendor lock-in and per-post cost |

**Consequences.** Easier: adding a platform. Harder: each adapter needs its own token lifecycle and tests. **Needs a human:** developer app registration and review for each direct platform.

---

## ADR-005: Hybrid news strategy: shared ingest plus per-plan selection, optional BYO key
**Context.** Requirement 5 asks whether each user should bring a news key or the system should be connected centrally. Per-user keys add onboarding friction. A single shared key hits quota as users grow, if each user triggers their own fetch.

**Decision.** Operator-funded **shared ingest** (keyless APIs, curated RSS and an optional paid key that is off by default) fills a de-duplicated `Article` store on an interval, with fetch volume proportional to **topics, not users**. Each plan **selects** from it, with LLM scoring on the user's own text key for a small shortlist. Users may add their own news key for extra sources.

| Option | User effort | Operator cost | Scales with |
|---|---|---|---|
| **A. Hybrid** | None | Low, bounded | Topics |
| B. Per-user keys only | High | None | Users (and onboarding drop-off) |
| C. One shared key, fetch per user | None | Grows linearly | Users (quota risk) |

**Consequences.** Easier: onboarding, cost control, consistent quality rules. Harder: someone curates source lists and topic presets (data, not code).

---

## ADR-006: AI artwork plus programmatic text overlay for posters
**Context.** Image models frequently misspell or garble text, which makes poster headlines unreliable and review-failure-prone.

**Decision.** The image model produces artwork only ("no readable text"). A Pillow renderer overlays the headline and source line from templates (safe area, contrast, bundled fonts, platform sizes).

**Trade-offs.** Less creative freedom than fully AI-designed posters. In return: always-correct text, consistent look, fewer review loops.
**Consequences.** We ship and license fonts and maintain templates. Revisit if users want richer layouts (HTML/CSS render-to-image is the likely next step).

---

## ADR-007: Deterministic verdict and a closed-by-default auto-post gate
**Context.** Auto-posting AI content about layoffs and hiring (real companies and people) carries legal and reputational risk. LLM "approve" outputs are not a safe control on their own.

**Decision.** The reviewer returns structured scores and issues. The **verdict** is computed in code from those. `may_autopublish(post, plan)` is one small, exhaustively tested function. It is **closed by default**: anything other than a clean `pass` above the plan's threshold, with no blocker issues and a topic that permits it, goes to manual approval. After the 2-round correction limit, a post goes to manual regardless of mode.

**Consequences.** Easier: auditing why a post was or was not auto-published. Harder: thresholds need tuning against real outputs. **The policy body is human-authored** (editorial risk tolerance).

---

## ADR-008: Secrets in Postgres with MultiFernet, key from environment
**Context.** The app stores many users' provider keys and social tokens.

| Option | Complexity | Security | Ops |
|---|---|---|---|
| **A. Fernet/MultiFernet column encryption, master key in env or secret manager** | Low | Good (rotation supported) | Low |
| B. Cloud KMS envelope encryption | Medium | Better | Cloud-specific |
| C. HashiCorp Vault for every secret | High | Best | Heavy |

**Decision.** A now, designed so B can replace the key provider later. Secrets are write-only in the API, redacted in logs, and hard-deleted on request.
**Consequences.** Master-key loss means loss of all secrets, so key backup is an operational requirement. Revisit when compliance or hosting demands KMS.

---

## ADR-009: JWT auth for a decoupled frontend
**Status:** Proposed. **Decided by owner:** refresh token in an httpOnly cookie.

**Decision.** Email login, short-lived access JWT, rotating refresh token with revocation, CORS allowlist. The **refresh token is set in an httpOnly, Secure, SameSite cookie** limited to the auth paths, so scripts in the browser can never read it. The **access token** is returned in the response body and kept in frontend memory. `refresh` and `logout` read or clear the cookie and are protected against cross-site requests (SameSite plus a required custom header). CORS allows credentials only for an exact allowlist of frontend origins. Local development uses same-site `localhost` ports.
**Consequences.** The frontend must send requests with credentials included, and an expired access token is renewed by calling `refresh`. If the frontend is ever hosted on a different site from the API, the cookie needs `SameSite=None; Secure`, and this decision should be revisited.

---

## ADR-010: Private object storage with signed URLs for posters
**Context.** Some publishers fetch images by URL, others take uploaded bytes.

**Decision.** Private S3-compatible bucket. Hand URL-based publishers a time-limited signed URL. Byte-based publishers get the object uploaded directly. A lifecycle rule expires images after the retention period.
**Trade-offs.** Signed URLs add expiry handling. Whether a specific platform accepts signed URLs is **unverified** and must be confirmed per adapter. If one does not, that adapter uses byte upload or a short-lived public path.
**Consequences.** No permanently public user content by default.
**Amended by ADR-011:** in free mode the default storage backend is a local volume, served through signed URLs by the web process. The S3-compatible backend remains available behind the same interface.

---

## ADR-011: Free launch with per-user quotas (no billing)
**Status:** Proposed · **Decided by owner:** launch completely free.

**Context.** The product launches free. AI inference is already paid by users through their own keys, so the operator's real costs are compute, storage, the shared news budget and hosting. Without a limiter, a few heavy or abusive users could exhaust a small host. Free hosting tiers also constrain what the architecture can assume (§17 of the system design).

**Decision.**
1. No billing or payment code in v1.
2. A `QuotaService` with configurable `QuotaPolicy` (default tier `free`), atomic conditional-update counters, per-user-timezone daily windows, `QuotaOverride` for operators, and `GET /me/usage/` for the frontend. Starting limits are in system design §17.2.
3. Registration modes (`open`, `invite`, `closed`), with `invite` recommended at launch.
4. Free-host operating rules: local-volume storage by default, retention jobs, a disk guard, per-source news budgets, `max_lateness` for downtime, and a threaded worker pool for network-bound pipelines.

| Option | Operator risk | Complexity | Future flexibility |
|---|---|---|---|
| **A. Free tier with configurable quotas** | Bounded by quotas | Low-medium | Tiers can be added as data |
| B. Fully unlimited | High (one heavy user can take down the host) | None | Quotas retrofitted under pressure |
| C. Free with hard-coded constants | Bounded | Low | Every change needs a release |

**Consequences.** Easier: protecting a small host, adding paid tiers later. Harder: every feature that consumes a limited resource must call the quota service, and each needs a test. Revisit when real usage shows which limits are too tight or too loose.

---

## ADR-012: In-app notifications only; accounts without email
**Status:** Proposed · **Decided by owner:** notifications are in-app only.

**Context.** No email provider means no email verification, no emailed password reset and no email alerts. Users who choose manual approval still need to find out when a post awaits them.

**Decision.**
1. A `Notification` table with a `Notifier` interface. Today the only implementation writes in-app rows. The frontend polls `GET /me/summary/` and `GET /notifications/unread-count/`.
2. Account recovery through 8 one-time hashed recovery codes shown at registration (`POST /auth/recover/`).
3. Noise control via `dedupe_key`. Retention is 60 days.

| Option | Reach | Cost | Complexity |
|---|---|---|---|
| **A. In-app only, recovery codes** | Only when the user opens the app | None | Low |
| B. In-app plus email | Better | Needs a provider and sending limits | Medium |
| C. In-app plus web push | Good | Needs frontend service worker and keys | Medium |

**Consequences.** Easier: no provider to configure, no email deliverability problems. Harder: pending approvals can go unseen, which the `on_missed_approval` policy (default `expire`) limits. Users who lose both password and recovery codes need operator-assisted recovery. Adding email or push later only means a new `Notifier` implementation.

**Also amends ADR-005:** the paid news key is optional and off by default. The default source set is keyless, with a per-source daily request budget.

---

## ADR-013: Beginner-readable code standard, with explicit DRF `APIView` classes
**Status:** Proposed · **Decided by owner:** top-level requirement, "only easy syntax; the entire codebase understandable by a beginner; don't compromise anything".

**Context.** The codebase must be readable by a beginner without cutting features. Several earlier choices (ViewSets, property-based tests, abstract interfaces) are idiomatic for experienced developers but hide behaviour behind framework magic or advanced syntax.

**Decision.**
1. Adopt the standard in [code-standard.md](code-standard.md): a defined Beginner Subset of Python, shape limits, one-way flow (views, services, models), eight named patterns, the same file layout in every app, and tests written as readable sentences.
2. For the API, use Django REST Framework in the **explicit style**: `APIView` classes with visible `get` and `post` methods, plain serializers, no ViewSets, routers or mixins.
3. Enforce the standard in CI (Ruff rules plus `scripts/check_readability.py`) and with a fresh-eyes review at the end of each phase.

| Option | Readability for a beginner | Maturity and ecosystem | Resume recognition |
|---|---|---|---|
| **A. DRF with explicit `APIView`** | High (each method is visible) | High (JWT, throttling, OpenAPI tooling) | High |
| B. DRF with ViewSets and routers | Medium (concise but implicit) | High | High |
| C. Django Ninja (function views) | Very high | Newer, fewer ready-made add-ons | Medium |

**Trade-offs.** Option A is more verbose than B, and C is shorter still. A was chosen because the verbosity is exactly what makes behaviour visible, and DRF's mature auth, throttling and OpenAPI tooling would otherwise need to be rebuilt by hand.
**Consequences.** More lines of code in places, by design. More documentation work each phase. The standard becomes a distinctive, explainable portfolio feature. Revisit if the verbosity becomes a maintenance burden.

---

## ADR-014: Demo mode with built-in fake providers
**Status:** Proposed · **Context:** the project is a resume showcase, and reviewers will not have the owner's API keys, a Buffer token or developer apps for social platforms.

**Decision.** `DEMO_MODE=true` swaps every external provider for a built-in fake that implements the same base class as the real adapter. Fakes are shared with the test suite. Demo output is labelled `demo_mode: true`, and the README states plainly that it is canned, not real AI output.

| Option | Reviewer effort | Honesty | Maintenance |
|---|---|---|---|
| **A. Fakes shared with tests, clearly labelled** | Three commands, no keys | High (labelled) | One implementation for demo and tests |
| B. Require real keys to try it | High | High | None |
| C. Hosted live demo | Low | Needs real accounts and cost | Hosting, abuse control (deployment is deferred) |

**Consequences.** Easier: anyone can run and understand the project, and the pipeline is exercised the same way in demo, tests and live mode. Harder: the fakes must stay faithful to the real adapters, which contract tests enforce. A hosted demo (option C) can be reconsidered when deployment is decided.
