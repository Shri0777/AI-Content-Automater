# AI Content Automator: Backend Build Plan (V4)

Status: **Phases 0 to 6 are built and verified against stub servers** (V3 preserved under the `legacy-v3` tag). Real AI providers and social platforms are **unverified-live** until someone runs them with real keys and registered apps. Next: Phase 7, the studio.
Scope: backend only (REST API + workers). The frontend is planned separately.

**Decided so far**
- **Top requirement: code a beginner can read.** Simple syntax everywhere, with no feature compromised. Enforced by CI. See [design/code-standard.md](design/code-standard.md).
- **Goal: a standout resume project.** Runs with no API keys through a demo mode, and every claim is measured. See [design/resume-showcase.md](design/resume-showcase.md).
- **Launch model: completely free**, in-app notifications only, per-user free limits.
- **Deployment is deferred.** Everything runs locally with Docker Compose for now.

**Design artifacts**
- [design/system-design.md](design/system-design.md): requirements, load estimate, architecture, scheduling, pipeline, newsroom, publishing, security, reliability, free-launch model (§17), readability and demo mode (§18).
- [design/code-standard.md](design/code-standard.md): the beginner-readable standard and how CI enforces it.
- [design/decisions.md](design/decisions.md): 14 ADRs.
- [design/test-strategy.md](design/test-strategy.md): test layers, critical-area tests, V3 regression guards.
- [design/resume-showcase.md](design/resume-showcase.md): what makes the project loud, demo mode, showcase checklist, talking points.
- Diagrams (FigJam): https://www.figma.com/board/WWElDdJRzbpW0FS0RiEAho (architecture, pipeline sequence, post lifecycle, data model, free-launch additions).

---

## 1. Context
The V3 app (Django, ~21.7k lines) failed on its first real runs: a template crash, an undefined variable, retries stuck in `queued`, Beat tasks that never registered. Hundreds of tests passed regardless because they mocked the real paths. It was also too broad to verify: about 1,400 lines of unused publishers, a no-op reconcile task, one global Buffer token shared by all users, a dead app and about 100 overlapping docs.

You authorised deleting the whole codebase. V4 is rebuilt around your requirements, and every claim is verified against stub servers that speak real wire formats. Nothing is reported as live-verified without real credentials.

## 2. Requirements and how each is met
| # | Requirement | Backend answer |
|---|---|---|
| 1 | Separate keys: image generation, and text generation (used for prompting the image model) | `ProviderCredential` with `kind = text \| image \| news`. The text key drives curation scoring, image-prompt writing and review. |
| 2 | Any AI model | Text via two adapters: any OpenAI-compatible service, or Anthropic (model name and optional `base_url`, ADR-015). Image via adapters (OpenAI-compatible, NVIDIA FLUX, fal). "Test connection" endpoint. |
| 3 | Link Buffer or social accounts directly, simply | One base class plus one adapter per platform. Buffer (paste a token) plus direct OAuth (LinkedIn, X, Meta). Two endpoints per link flow. |
| 4 | Schedule: number of posts, timing, weekdays | `ScheduleRule` (days, local times, timezone) materialised into idempotent `PostSlot` rows. |
| 5 | News API, user-friendly | **Hybrid:** shared ingest from keyless sources and curated RSS (an optional paid key is off by default), cached once per topic and budgeted per source, plus an optional user-supplied news key. |
| 6 | User requirements drive news search | `ContentPlan.requirements` and `Topic`s drive shortlist selection and LLM scoring. |
| 7 | Text API writes the image prompt, image API renders | Pipeline stages 4 and 5. Poster text is overlaid programmatically (ADR-006). |
| 8 | Verify and correct | Structured AI review, deterministic verdict, up to 2 correction rounds. |
| 9 | Auto-post or manual approval | `approval_mode`. Auto mode passes a **closed-by-default gate** (ADR-007). Anything uncertain goes to manual approval. |
| 10 | Very high-quality news (jobs, layoffs, Linux tips, AI news) | Per-topic source policy, freshness window, de-duplication, full-text extraction, LLM credibility scoring, used-article ledger, citations, evergreen handling for tips, stricter gate for sensitive topics. |
| 11 | **Beginner-readable code, nothing compromised** | The Beginner Subset, shape limits, one-way flow, 8 patterns, CI enforcement, per-phase fresh-eyes review. ([code-standard.md](design/code-standard.md)) |
| 12 | **Resume-grade showcase** | Demo mode with fake providers, Swagger walkthrough, case study, measured claims only. ([resume-showcase.md](design/resume-showcase.md)) |

## Beginner-readable code (summary)
- **Allowed:** variables, functions, `if`, `for`, simple classes (one level of inheritance), specific `try/except`, one-level list comprehensions, simple type hints.
- **Avoided:** `async`, metaclasses, our own decorators, `*args/**kwargs`, `lambda`, generators, signals, DRF ViewSets and routers, `functools`/`itertools` tricks.
- **Shape:** files 200 lines or fewer (hard cap 250), functions 20 lines or fewer (hard cap 30), complexity 7 or lower, 5 or fewer parameters.
- **Flow:** views call services, services call models and adapters, tasks call services. No business logic anywhere else.
- **Same layout in every app:** `models.py`, `serializers.py`, `views.py`, `urls.py`, `services.py`, `tasks.py`, `tests/`, `README.md`.
- **Enforced by:** Ruff rules, `scripts/check_readability.py`, a fresh-eyes review at the end of each phase, and a `docs/CODE-TOUR.md` that must match the code.
- **Four named exceptions** to the standard, each isolated and commented: the dispatcher's `skip_locked`, the quota counter's atomic update, the encryption helper, and the post tasks' catch-and-re-raise that marks a crashed post `failed` instead of leaving it stuck.

## Free launch model (decided)
- **No billing, no payment code.** Users bring their own AI keys, so quotas protect only the operator's compute, storage, shared news budget and outbound posting volume. Limits are configurable data (`QuotaPolicy`), so paid tiers can be added later without a redesign.
- **Notifications are in-app only.** A `Notification` table behind a `notify(...)` helper. The frontend polls `GET /me/summary/`.
- **No email means recovery codes.** 8 one-time codes at registration reset a password. Registration modes (`open`, `invite`, `closed`) let you control growth while free. Decided for launch: `invite`.
- **Deployment is deferred.** The design still assumes an always-on host later, and handles downtime through `max_lateness` (stale slots are skipped, never posted late).

**Free limits per user (proposed starting defaults, editable without a release)**
| Resource | Limit |
|---|---|
| Active content plans | 3 |
| Topics per plan | 6 |
| Linked social accounts | 5 |
| Posts generated per day (all plans) / per plan | 6 / 4 |
| Schedule horizon | 14 days |
| Manual "generate now" runs | 5 per day |
| Regenerations per post | 3 |
| Credentials | 1 active per kind (text, image, news) |
| News preview requests | 30 per day |
| API requests | 120 per minute (auth endpoints: 10 per minute per IP) |
| Poster storage / retention | 250 MB per user / 30 days (text and history are kept) |

Why each limit exists, how it is enforced atomically, and the retention rules are in [design/system-design.md §17](design/system-design.md).

## Resume goal (summary)
- **Demo mode** (`DEMO_MODE=true`): built-in fake text, image, news and social providers plus seed data, so anyone can run the full pipeline in three commands with no keys. Output is labelled `demo_mode: true`, and the README says plainly it is canned content.
- **Swagger UI** is the demo surface, since the frontend is separate.
- **Case study** of the V3-to-V4 rebuild, a CI badge, coverage on critical modules, and diagrams in the README.
- **Honesty rule:** numbers appear on the resume only after we measure them. Live integrations are claimed only after a human runs them with real credentials.

## 3. Tech stack
| Concern | Choice |
|---|---|
| API | Django 5, Django REST Framework in the **explicit style** (`APIView` classes with `get`/`post`), drf-spectacular (OpenAPI 3) |
| Auth | Email login, JWT access plus rotating refresh, CORS allowlist |
| Database | PostgreSQL |
| Jobs | Celery, Redis (broker only), DB-claimed schedule |
| LLM | Own adapters (ADR-015): OpenAI-compatible over httpx, Anthropic's official library; JSON answers checked with DRF serializers and one repair round |
| Images | One base class plus one adapter per image provider, Pillow poster renderer |
| Extraction | `trafilatura` used in one file behind `extract_article_text(...)`, over an SSRF-safe HTTP client |
| Storage | Local volume by default, S3-compatible optional behind the same interface. Signed URLs. Retention jobs. |
| Quotas | `check_quota` / `use_quota` with atomic conditional-update counters, `QuotaPolicy` and `QuotaOverride` data |
| Secrets | Fernet behind `encrypt_text` / `decrypt_text`, key from env |
| Quality | pytest-django, freezegun, stub servers, ruff (with readability rules), bandit, pip-audit, GitHub Actions |
| Readability gate | Ruff rules plus `scripts/check_readability.py`, both run in CI |
| Demo | `DEMO_MODE` with built-in fake providers (the same stubs the tests use) |
| Local run | Docker Compose: web, worker, beat, postgres, redis. **Production deployment deferred.** |

## 4. Layout
```
config/            settings (base/dev/prod via django-environ), celery.py, urls.py
core/              encrypt_text/decrypt_text, the error format, health check (safe web client later)
accounts/          User, auth, recovery codes, invite codes, /me
quotas/            free-tier limits as data, race-safe daily counters, /me/usage
notifications/     notify(), in-app notification endpoints, nightly cleanup
credentials/       ProviderCredential, connection tests
social/            SocialAccount, base publisher + one subclass per platform (buffer, linkedin, x, meta)
planning/          ContentPlan, Topic, ScheduleRule, PostSlot, slot materialiser, dispatcher
newsroom/          news sources (one subclass each), Article, curation, quality scoring, topic presets
studio/            ask_text_model, image providers, poster renderer, drafting, review/correction, auto-post gate
publishing/        Publication, idempotent publish, reconcile, token refresh
demo/              fake text, image, news and social providers plus seed data (used by DEMO_MODE and tests)
docs/CODE-TOUR.md  reading order, glossary, the 8 patterns, one request followed end to end
scripts/           check_readability.py, smoke_check.py, demo_walkthrough.py (Phase 2)
schema/            openapi.yaml, the saved API contract checked by a test
```
Every app contains the same files: `models.py`, `serializers.py`, `views.py`, `urls.py`, `services.py`, `tasks.py`, `tests/`, `README.md`.

## 5. Data model (key tables)
- **User**: email, default timezone.
- **ProviderCredential**: user, kind (text/image/news), adapter, model, base_url, encrypted key (write-only), status, last_verified_at.
- **SocialAccount**: user, platform, link_method (buffer/oauth), external id, encrypted tokens, expires_at, scopes, status (active, needs_reauth, revoked).
- **ContentPlan**: user, requirements (free text), approval_mode, auto_post_min_score, on_missed_approval, max_lateness, target accounts, image style, ai_label_enabled (default true), ai_label_text, paused.
- **Topic**: plan, name, kind (news/evergreen), query terms, source policy, freshness window, weight.
- **ScheduleRule**: plan, days_of_week, times, timezone. **PostSlot**: plan, rule, publish_at, generate_at, claimed_until, `UNIQUE(plan, publish_at)`.
- **Article**: url hash (unique), title, source, source tier, published_at, extracted text (TTL), scores. **ArticleUse**: (plan, article).
- **Post**: slot, topic, article, status, skip_reason. **PostVersion** (immutable): caption, headline, image prompt, image key. **Review**: version, scores, issues, verdict.
- **Publication**: post, account, idempotency key (unique), external id, status (including `ambiguous`).
- **GenerationStep**: post, stage, model, prompt version, tokens, cost, duration, error (the audit trail).
- **Notification**: user, kind, title, body, related post/plan/account, created_at, read_at, dedupe_key.
- **QuotaPolicy** (tier limits), **QuotaUsage** (user, resource, window_start, used), **QuotaOverride** (user, resource, limit).
- **InviteCode** (single use) and **RecoveryCode** (hashed, single use).
- **SourceBudget**: adapter, day, requests_used, cap.

The allowed status changes are one dict (`ALLOWED_TRANSITIONS`) used by the model, the API and the tests.

## 6. Pipeline per due slot (summary)
Dispatch (claim with lease) → research (shared Article store, heuristics, LLM scoring of a short list) → draft → image prompt → image → poster overlay → review and correct (max 2 rounds) → approval gate → publish at `publish_at` (idempotent, reconcile on ambiguity). Generation starts `lead_time` before `publish_at` so the post is ready on time. Full detail, error classes and failure modes are in [design/system-design.md](design/system-design.md).

## 7. API surface (v1, owner-scoped)
- `POST /auth/register` (with an invite code when the mode is `invite`), `login` (returns the access token and sets the refresh token in an httpOnly cookie), `refresh` (reads that cookie), `logout` (clears it), `POST /auth/recover/` (recovery code), `POST /auth/recovery-codes/` (regenerate)
- `GET/PATCH /me`, `GET /me/usage/` (every limit and current usage), `GET /me/summary/` (unread count, posts awaiting approval, accounts needing attention)
- `/credentials/` CRUD, `POST /credentials/{id}/test/` (keys write-only)
- `/social/accounts/`, `POST /social/link/{platform}/start/`, `GET /social/link/{platform}/callback/`, `POST /social/link/buffer/`, `DELETE /social/accounts/{id}/`
- `/plans/` CRUD with nested topics and schedule rules, `POST /plans/{id}/pause|resume/`, `GET /plans/{id}/upcoming/`
- `/posts/` list/detail with versions, review and steps. `POST /posts/{id}/approve|reject|regenerate/`, `PATCH` caption (creates a new version).
- `POST /plans/{id}/generate-now/`, `GET /news/preview/?topic=`
- `GET /notifications/` (`?unread=true`), `GET /notifications/unread-count/`, `POST /notifications/{id}/read/`, `POST /notifications/read-all/`
- `/health/`, `/schema/`, `/docs/` (Swagger UI)

Conventions: cursor pagination, problem-details errors, `Idempotency-Key` on mutating POSTs, `202` plus a pollable resource for long operations, OpenAPI snapshot test.

## 8. Phases and exit criteria
Work is built as a **walking skeleton first** (Phase 2), then deepened. That gives a runnable demo early and keeps every later phase small enough to understand.

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **0 Safety** | Branch `rebuild/backend-v4`. Checkpoint commit of the current tree, tag `legacy-v3`. Then delete old code, about 100 docs and tracked `.kiro/*.bak*` files. | Old code recoverable from the tag. Clean tree on the new branch. |
| **1 Foundation** | `config/`, `core/`, `accounts/`, pinned deps, local Docker Compose, CI with the readability gate, OpenAPI snapshot, quota functions, registration modes, recovery codes, `Notification` model, `docs/CODE-TOUR.md` skeleton | Clean-checkout CI green (including readability gate). `check --deploy` green. Auth, recovery and invite flows work end to end. Quota boundary and race tests pass. Fresh-eyes review list is empty. |
| **2 Walking skeleton (demo mode)** | One thin path using the fake providers: register, save credentials, create a plan, generate-now, poster image, manual approve, publish to the fake publisher. `scripts/demo_walkthrough.py`, Swagger UI. | A clean checkout runs the demo with **no API keys** in three commands. The scripted end-to-end test passes. |
| **3 Credentials and models** | Real adapters: OpenAI-compatible and Anthropic text, OpenAI-compatible, NVIDIA FLUX and fal images, connection tests, encrypted keys, SSRF-safe web client | User saves keys and sees them verified against stubs. Keys never appear in responses or logs. |
| **4 Social linking** | Base publisher, Buffer, then LinkedIn, X, Meta, token refresh | Link, publish, refresh, revoke against stub providers. Two-user token isolation test. |
| **5 Planning and scheduling** | Plans, topics, rules, slot materialiser, dispatcher, `max_lateness` | Named daylight-saving test cases, dispatcher race tests, crash-lease recovery, outage simulation skips stale slots with one aggregated notification. |
| **6 Newsroom** | Keyless sources, extraction, curation, scoring, presets (jobs, layoffs, Linux tips, AI news), per-source budgets, demand-driven ingest | Quality gates behave on fixtures. "Nothing good enough" yields `skipped`, never filler. A source stops at its daily cap and plans fall back to cache. |
| **7 Studio** | Drafting, image prompt, poster renderer, review and correction | Golden-image tests. Verdict logic exhaustive. Prompt-injection fixtures pass. |
| **8 Publishing and approval** | Auto-post gate, idempotent publish, reconcile, all in-app notification events | Concurrent publish makes one external call. Ambiguity handling verified. Gate tested as an exhaustive readable table. |
| **9 Hardening** | Throttles, SSRF suite, retention jobs, security review, local load test, docs | A burst of about 100 pipelines passes on the local Compose setup against fake providers. Security review findings fixed. |
| **10 Resume packaging** | README, diagrams in `docs/`, `docs/CASE-STUDY.md`, badges, demo recording, measured resume bullets | A newcomer runs the demo in three commands. Every number cited is measured. |
| **Later (not scheduled)** | Production deployment, frontend integration, live-provider verification | Decided with you after Phase 10. |

**Phase 4 notes (built 2026-11-17).** Buffer (API key, channels found automatically), X (OAuth 2.0 with PKCE, rotating refresh tokens), LinkedIn (member posts) and Facebook Pages. Each adapter follows that platform's documentation, read on 2026-11-17 and linked at the top of its file. Decisions and limits:
- **Instagram is deferred.** Meta downloads Instagram images from a public URL and needs JPEG. This uses the signed poster link built for Buffer, so it can follow once a public address exists.
- **LinkedIn tokens cannot be refreshed** by self-serve apps (60 days). Users get a warning a week before expiry and relink. Not yet confirmed live: that `/v2/userinfo`'s `sub` is the id in `urn:li:person:<id>`.
- **Buffer posts go out 2 minutes after publishing** (`customScheduled`), so Buffer has time to download the poster. Phase 5 will pass the slot's real time instead.
- **Refresh safety:** refreshing locks the account's row, so a single-use refresh token is never sent twice. A test proves two simultaneous workers make one refresh call.
- **Revoke on unlink:** X's revoke call is used. LinkedIn and Meta revoke calls were not verified, so for them only our copy of the tokens is deleted.
- **Ambiguous outcomes and `check_status`** (ADR-004's reconcile) are Phase 8 work.

**Phase 5 notes (built 2026-11-17).** Schedule rules (weekdays, local times, IANA timezone) become `PostSlot` rows up to the 14-day horizon (hourly, and right after a plan or schedule changes). A dispatcher runs every minute: it skips slots that are too late, then claims due slots with `SKIP LOCKED` and a 5-minute lease and starts their posts. Approved scheduled posts publish at `publish_at`, and late approvals expire or are held depending on `on_missed_approval`. Tests cover nine named daylight-saving cases (New York, London, Sydney, Kolkata), three dispatchers racing over 20 slots, crash-lease recovery, and an outage that skips five stale slots with one notification. Decisions:
- **`lead_time_minutes` is a plan setting, default 60 (15 minutes to 1 day).** The design's 20 minutes leaves almost no time for manual approval.
- **Pausing removes waiting slots; resuming remakes them** and counts toward the active-plans limit again.
- **Posting times per day are checked against `posts_per_plan_per_day`** when a schedule is saved, so a schedule cannot promise more posts than the limit allows. A slot that still hits a limit is skipped with `quota_reached` and one notification per day.
- **Buffer still sends about 2 minutes after the slot time**, because Buffer has to download the poster first.

**Phase 6 notes (built 2026-11-17).** Keyless sources: each preset reads sites' own RSS or Atom feeds and a Hacker News search (presets.py lists them). Ingest runs every 30 minutes for presets that active plans use, and on demand when the last read is over 30 minutes old. Quality gates follow §7.2 in order, ending with the user's own text model rating a shortlist of 5. Decisions:
- **Google News RSS and VentureBeat are left out.** Both answered automated requests with HTTP 429 on 2026-11-17, and Google News links point to Google's own redirect pages, not the article.
- **Article pages are read only where `robots.txt` allows our reader *and* the common AI crawlers** (GPTBot, ClaudeBot, anthropic-ai, Google-Extended, CCBot). Several news sites block AI crawlers, so for them only the text their own feed publishes is used.
- **Text extraction uses Python's own HTML parser** instead of trafilatura (one fewer large dependency). defusedxml was added because feeds are untrusted XML.
- **An article needs at least 280 characters of text.** TechCrunch's tag feeds publish one line and its pages are closed to AI readers. So layoffs and hiring also read two **broad** full-text feeds (The Register and Computerworld), keeping only items that mention the preset's keywords.
- **Articles are stored once per address *and* preset.** A shared feed must not file a story only under whichever preset read it first. The used-article check compares addresses, so a plan never posts the same story under two topics.
- **Live check on 2026-11-17** (Docker, real internet): AI news had 31 usable articles, Linux tips 51, job hiring 20 and layoffs 2. Layoffs is thin on free sources; on days without a qualifying story, those posts are skipped.
- **Not yet built:** a user's own paid news key (later, with the other APIs) and the 30-day text retention job (Phase 9).

Each phase also ends with the definition of done in [design/test-strategy.md](design/test-strategy.md#7-definition-of-done-per-phase): green tests, the readability gate, the fresh-eyes review, and an updated code tour, plus a review of the final diff.

## 9. Verification (summary)
Unit, integration (real Postgres, Redis and Celery worker), contract (OpenAPI snapshot, provider fixtures), scripted end-to-end API walk in demo mode, failure injection, security, load, readability gate. Details and V3 regression guards: [design/test-strategy.md](design/test-strategy.md).

## 10. Needs a human (nothing here will be fabricated)
- Developer app registration (and app review where needed) for LinkedIn, X and Meta.
- Real text and image model keys and a Buffer token for live checks. A paid news key is optional and off by default.
- For Buffer: a server reachable from the internet (`PUBLIC_API_URL`), because Buffer downloads the poster itself.
- Until then, live generation, linking and publishing are verified **only against stubs and fakes**, and docs mark them **unverified-live**.
- The **auto-post gate policy** (Phase 8) encodes editorial risk tolerance. I will build it myself with a safe, closed-by-default policy, and list it in the review notes so you can read it and adjust the thresholds after the build.
- Deployment and hosting choices, when you are ready.

## 11. Open questions
**Decided:**
- Notifications are in-app only. Free launch with per-user limits. Beginner-readable code standard. Resume-focused showcase. Deployment deferred.
- **Login tokens:** the refresh token lives in an httpOnly cookie and the access token stays in frontend memory (ADR-009). The frontend must send requests with credentials included.
- **Registration:** `invite`-only at launch (single-use invite codes). `open` and `closed` stay available as a setting.
- **AI-assisted label:** optional per plan, defaults to on (`ai_label_enabled`, `ai_label_text`). Captions are shortened to fit before the label is added, so the label is never cut off.
- **Ownership:** single owner per plan, credential and social account. No shared workspaces.

Defaults I'll apply unless you say otherwise:
- The optional paid news key stays **off**. Only keyless sources are used.
- Python and Django versions: newest stable releases at setup time.

Nothing is blocking Phase 0 or Phase 1.

## 12. How to proceed
When you say go, I start **Phase 0** (branch, checkpoint commit, tag, then deletion of the old code) and continue phase by phase, verifying each one. Until then, nothing in the existing codebase changes.
