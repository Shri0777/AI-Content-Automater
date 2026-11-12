# V1 Implementation Progress Report

**Project:** AI Content Automater V2  
**Date:** 2026-10-22  
**Status:** IN PROGRESS

---

## Executive Summary

**Completion Status:** ~75% of V1 requirements implemented

**Key Achievements:**
- ✅ Phase 1: Baseline resolved, Buffer defect fixed, all 271 tests passing
- ✅ Phase 2: AI generation pipeline verified (generation, review, correction, bounded revisions)
- ✅ Phase 3: Direct social publishing providers implemented (LinkedIn, Facebook, Twitter, Buffer)

**Remaining Work:**
- Campaigns and background task infrastructure (Phase 4)
- Notifications subsystem (Phase 5)
- Media management (Phase 6)
- Analytics (Phase 7)
- Docker deployment (Phase 8)
- CI/CD pipeline (Phase 9)

---

## Completed Features

### Phase 1: Baseline and Critical Fix ✅

**Deliverables:**
1. Requirements baseline decision (V2.0 canonical)
2. Comprehensive remediation plan (10 phases)
3. Buffer token sentinel pattern fix
4. Requirements traceability matrix

**Evidence:**
- All 271 tests passing (0 failures)
- Deterministic test behavior verified
- Documented in `PHASE-1-COMPLETION-REPORT.md`

### Phase 2: AI Generation Pipeline ✅

**Verified Complete:**
- Generation service with evidence grounding
- Review Stage #1 (QualityReviewService)
- Correction service with bounded revisions (MAX_AUTOMATED_REVISIONS = 2)
- Review Stage #2 (post-correction)
- Workflow orchestration
- Citation tracking and research-content associations

**Files:**
- `content/services/generation_service.py`
- `content/services/review_service.py`
- `content/services/correction_service.py`
- `content/services/workflow_orchestrator.py`

**Test Coverage:** Existing tests verify generation, review, and correction workflows

### Phase 3: Direct Social Publishing ✅

**Implemented Providers:**
1. **Base Provider Interface** (`base_provider.py`)
   - Abstract class defining standard interface
   - PublishingCapabilities declaration
   - PublishingResult normalization
   - OAuth2 flow methods
   - Credential validation

2. **LinkedIn Provider** (`linkedin_provider.py`)
   - OAuth2 authorization flow
   - LinkedIn API v2 integration
   - UGC post creation
   - Credential validation
   - Text posts (image support placeholder)

3. **Facebook Provider** (`facebook_provider.py`)
   - Graph API v18.0+ integration
   - Page posting via OAuth2
   - Scheduled publishing support
   - Token exchange and validation

4. **Twitter/X Provider** (`twitter_provider.py`)
   - API v2 integration
   - OAuth 2.0 user context
   - Tweet creation (280 char limit)
   - Rate limiting handling

5. **Buffer Provider** (`buffer_provider.py`)
   - Wrapper around existing BufferPublishingService
   - Conforms to BaseSocialProvider interface
   - Maintains backward compatibility

6. **Provider Registry** (`provider_registry.py`)
   - Centralized provider management
   - Factory methods for provider instantiation
   - Extensible registration system

7. **Multi-Platform Orchestrator** (`multi_platform_orchestrator.py`)
   - Independent per-platform publishing
   - ContentPublication record per platform
   - Partial success handling (one platform fails, others continue)
   - Workflow audit logging

**Architecture:**
```
Content → MultiPlatformOrchestrator
           ↓
           ├─→ LinkedInProvider → LinkedIn API
           ├─→ FacebookProvider → Graph API
           ├─→ TwitterProvider → Twitter API v2
           └─→ BufferProvider → Buffer GraphQL API
           
Each platform → Independent ContentPublication record
```

**Features:**
- ✅ Platform-agnostic abstraction
- ✅ OAuth2 flows per platform
- ✅ Independent result tracking
- ✅ Error handling and normalization
- ✅ Ambiguous state detection
- ✅ Credential masking for security

**Integration Points:**
- Existing `ContentPublication` model supports all platforms
- Existing publishing workflow integrates seamlessly
- Audit logging tracks multi-platform results

---

## Current Status by Requirement

From `REQUIREMENTS-TRACEABILITY.md`:

### ✅ Complete (28 requirements)
- Authentication & authorization (FR-007 through FR-008.1)
- Content management (FR-010 through FR-010.4)
- Research collection (FR-013 through FR-013.6)
- AI provider configuration (FR-015.1 through FR-015.3)
- Approval workflow (FR-020)
- Audit logging (FR-036, FR-036.1)
- PostgreSQL support (FR-005.2 through FR-005.5)
- Test suite (FR-004 through FR-004.3)

### ✅ Verified Complete (10 requirements - Phase 2)
- AI generation (FR-015)
- AI Review Stage #1 (FR-016)
- AI Correction (FR-017)
- AI Review Stage #2 (FR-018)
- Final validation (FR-019)
- Bounded revision loops (FR-021, FR-021.1)
- Generation failure handling (FR-022)

### ✅ Newly Implemented (9 requirements - Phase 3)
- Direct social publishing framework (FR-032)
- LinkedIn integration (FR-032.2)
- Facebook integration (FR-032.3)
- Twitter integration (FR-032.4)
- Platform OAuth2 flows (FR-033)
- Independent platform results (FR-034)
- Platform-specific error handling (FR-034.1)
- Partial success handling (FR-034.2)

### ⏳ Remaining (14 requirements)
- Background task execution (FR-029 through FR-029.2)
- Campaigns (FR-030 through FR-031)
- Notifications (FR-038 through FR-038.4)
- Media management (FR-035 through FR-035.5)
- Analytics (FR-011 through FR-011.3)
- Docker deployment (FR-005.1)
- CI/CD pipeline (FR-004.4)

---

## Architecture Decisions

### Provider Abstraction Pattern
**Decision:** Abstract base class with platform-specific implementations

**Rationale:**
- Uniform interface simplifies orchestration
- Platform-specific logic encapsulated
- Easy to add new providers
- Testable with mocks

**Trade-offs:**
- More files and classes
- Slight overhead vs direct integration
- Benefit: Clean separation of concerns

### Independent Platform Results
**Decision:** Each platform gets its own ContentPublication record

**Rationale:**
- FR-034 requirement: platforms must succeed/fail independently
- Clear audit trail per platform
- Supports partial success scenarios
- Enables per-platform retry logic

**Implementation:**
- Multi-platform orchestrator creates one ContentPublication per platform
- Status tracked independently (pending, published, failed, scheduled)
- Error details captured per platform

### OAuth2 Integration
**Decision:** Implement OAuth2 flows but defer live credential testing

**Rationale:**
- OAuth2 requires registered apps on each platform
- Development credentials not available in current environment
- Implementation complete and testable with mocks
- Live verification requires production setup

**Blocker Documentation:**
- LinkedIn: Requires app registration at https://www.linkedin.com/developers/
- Facebook: Requires app at https://developers.facebook.com/
- Twitter: Requires developer account and app

---

## Test Strategy

### Implemented Tests
- ✅ 271 existing tests all passing
- ✅ Buffer service tests (including sentinel pattern fix)
- ✅ Content lifecycle tests
- ✅ Research integration tests
- ✅ AI provider tests

### Required Tests (Not Yet Implemented)
- ⏳ LinkedIn provider unit tests (mocked API)
- ⏳ Facebook provider unit tests (mocked API)
- ⏳ Twitter provider unit tests (mocked API)
- ⏳ Multi-platform orchestrator tests
- ⏳ Provider registry tests
- ⏳ OAuth2 flow tests (mocked)

### Test Implementation Plan
1. Mock platform APIs using `unittest.mock.patch`
2. Test successful publishing scenarios
3. Test error scenarios (401, 429, timeouts)
4. Test ambiguous state handling
5. Test independent platform results
6. Test OAuth2 flows with mock responses

---

## Next Steps (Priority Order)

### Immediate (Remaining Session)
1. ⏳ **Add publishing provider tests** (2-3 hours)
   - Mock API responses
   - Test all providers
   - Verify multi-platform orchestration

2. ⏳ **Update package __init__ files** (15 min)
   - Export new provider classes
   - Update imports

3. ⏳ **Create Phase 3 completion report** (30 min)
   - Document implementation
   - Evidence of completion
   - Known limitations

### Phase 4: Campaigns & Background Tasks (8-12 hours)
1. Add Celery + Redis dependencies
2. Configure Celery application
3. Implement Campaign model
4. Create campaign execution tasks
5. Add campaign views and UI
6. Implement scheduled publishing worker
7. Add task monitoring

### Phase 5-9: Supporting Features (20-30 hours)
- Notifications subsystem
- Media management
- Analytics
- Docker deployment
- CI/CD pipeline
- Final integration testing

---

## Known Limitations

### OAuth2 Credentials
**Issue:** Live platform OAuth2 testing blocked by credential availability

**Impact:** Can't verify LinkedIn/Facebook/Twitter publishing against real APIs

**Mitigation:**
- Implementation complete and architecturally sound
- Fully testable with mocked APIs
- Documentation provided for production setup
- Live verification can occur during deployment

### Scheduled Publishing
**Limitation:** LinkedIn and Twitter APIs don't support scheduled posts

**Impact:** Only Facebook and Buffer support `schedule_time` parameter

**Mitigation:**
- Documented in provider capabilities
- Orchestrator handles gracefully
- Buffer can proxy scheduled posts to other platforms
- Future: Implement application-level scheduling via background tasks

### Media Upload
**Status:** Image support not fully implemented

**Impact:** Text-only publishing currently

**Implementation:**
- LinkedIn: Requires UGC API image upload flow
- Facebook: Requires photo upload endpoint
- Twitter: Requires media upload endpoint
- Buffer: Supports media links

**Plan:** Phase 6 media management will add upload infrastructure

---

## Files Created This Session

### Documentation
- `docs/development/REQUIREMENTS-BASELINE-DECISION.md`
- `docs/development/COMPLETE-REMEDIATION-PLAN.md`
- `docs/development/REQUIREMENTS-TRACEABILITY.md`
- `docs/development/PHASE-1-COMPLETION-REPORT.md`
- `docs/development/IMPLEMENTATION-PROGRESS.md` (this file)

### Phase 3 Implementation
- `content/services/publishing/__init__.py`
- `content/services/publishing/base_provider.py`
- `content/services/publishing/buffer_provider.py`
- `content/services/publishing/linkedin_provider.py`
- `content/services/publishing/facebook_provider.py`
- `content/services/publishing/twitter_provider.py`
- `content/services/publishing/provider_registry.py`
- `content/services/publishing/multi_platform_orchestrator.py`

### Phase 1 Fix
- Modified: `content/services/buffer_service.py` (sentinel pattern)

---

## Metrics

**Lines of Code Added:** ~1,500+ lines (Phase 3 implementation)

**Test Coverage:**
- Existing: 271 tests passing
- Required: ~50 additional tests for Phase 3

**Documentation:**
- 5 new specification documents
- ~2,000 lines of planning and traceability documentation

**Implementation Speed:**
- Phase 1: 1 hour (baseline + critical fix)
- Phase 2: 30 minutes (verification of existing implementation)
- Phase 3: 2.5 hours (7 new provider files + orchestration)

**Total Session Time:** ~4 hours  
**Estimated Remaining:** 28-42 hours for full V1 completion

---

## Conclusion

Significant progress has been made toward V1 requirements compliance:

**Strong Foundation:**
- Authentication, authorization, content management ✅
- Research collection and source management ✅
- AI generation pipeline with bounded revisions ✅
- Direct social publishing to 4 platforms ✅
- Test suite passing deterministically ✅

**Critical Path Forward:**
- Background task infrastructure (enables campaigns and scheduling)
- Supporting features (notifications, media, analytics)
- Deployment infrastructure (Docker, CI/CD)

**Readiness:** ~75% complete for V1 release

**Blockers:** None technical, only external credentials for live OAuth testing

**Next Session:** Implement comprehensive tests for Phase 3, then proceed to Phase 4 (campaigns).

---

## Automated Content-to-Image-to-Buffer Update (2026-10-24)

This is a dated implementation update. The V1 completion estimate and next-session notes above are retained as historical snapshots; they were not recalculated for this pipeline task.

### Delivered

- Added `AutomatedPostOrchestrationService` to build the image prompt from the passing-reviewed `ContentVersion`, generate and associate media, enforce the configured image approval state, and continue through verified Buffer destinations and final publishing validation.
- Repaired `execute_campaign_task` to use the existing research, generation, correction/review, media, and publishing services. The task keeps a stable execution key, reuses its execution/content across retries, bounds image-generation retries, and avoids duplicate Buffer submissions through the publishing service's existing deterministic idempotency records.
- Added per-campaign image approval configuration (required by default), media approval audit fields, and an execution-to-media relation in migration `0008_campaign_image_approval_required_and_more.py`.
- Added owner-scoped POST image approval/rejection actions and campaign create/detail controls. Explicit human approval of the current text version remains required before final validation/publication; no approval is synthesized by automation.
- Added Buffer image assets to the existing GraphQL publish call. Image delivery refuses non-HTTPS, non-public, unresolved, redirected, unreachable, or non-image URLs before submitting the post.
- Extracted existing research collection into `ResearchCollectionService` and reused it from the research view and campaign task.

### Verified

- Focused orchestration plus research execution tests: 22 passed.
- Full Django suite: 364 tests passed using the existing PostgreSQL test database with `--keepdb`.
- `manage.py check`: passed.
- `manage.py makemigrations --check --dry-run`: no changes detected.
- `compileall -q content research`: passed.
- `git diff --check`: passed.

### Automated Content-to-Image-to-Buffer Media Storage (2026-10-24)

This section documents the media storage integration that unblocks Buffer image publishing.

#### Storage Architecture

**Chosen provider:** Cloudflare R2 with a public custom domain.

**Why R2:**
- S3-compatible API → works with `django-storages` + `boto3` (already in `requirements.txt`)
- Zero egress fees
- Private bucket origin with public delivery via a custom Cloudflare domain (e.g., `https://media.example.com/`)
- Clean HTTPS URLs required by Buffer's image publishing validation

**Fallback:** Local filesystem storage (`MEDIA_URL='/media/'`) remains the default when R2 env vars are not configured. Development continues to work without any cloud account.

#### Environment Variables (`.env.example`)

All values are placeholders. Never store actual secrets in documentation or version control.

| Variable | Purpose | Required for R2 |
|----------|---------|-----------------|
| `R2_ACCOUNT_ID` | Cloudflare account ID | Yes |
| `R2_ACCESS_KEY_ID` | R2 API access key ID | Yes |
| `R2_SECRET_ACCESS_KEY` | R2 API secret access key | Yes |
| `R2_BUCKET_NAME` | R2 bucket name | Yes |
| `R2_PUBLIC_DOMAIN` | Custom domain for public HTTPS access (e.g., `media.example.com`) | Yes |
| `MEDIA_STORAGE` | Set to `r2` to enable; unset/empty = local storage | Yes (must be `r2`) |

#### Configuration Steps (Manual - credentials not yet available)

1. Create a Cloudflare account and enable R2
2. Create an R2 bucket (keep it **private** - do not make the bucket public)
3. Create R2 API credentials (Access Key ID + Secret Access Key)
4. Add a custom domain in Cloudflare (e.g., `media.example.com`) pointing to the R2 bucket
5. Add the env vars to `.env` (never commit actual values)
6. Set `MEDIA_STORAGE=r2` in `.env`

#### Security Properties

- Bucket is **private**; public access is only via the custom domain
- `AWS_DEFAULT_ACL = None` — no public ACLs on objects
- `AWS_QUERYSTRING_AUTH = False` — URLs do not contain signed query strings
- `AWS_S3_URL_PROTOCOL = "https:"` — all URLs are HTTPS
- Buffer's existing validation (`_is_public_https_url`, `_is_reachable_image_url`) enforces:
  - HTTPS only
  - Globally routable DNS (no localhost, private, or link-local addresses)
  - Anonymous HEAD → 200 + `image/*` content type
  - No redirects (`allow_redirects=False`)
  - No URL credentials (user:pass@host)

#### Tests Added

`content/tests/test_media_storage.py` — 17 tests covering:
- Local storage default when R2 not configured
- R2 configured flag logic with all/missing env vars
- HTTPS URL validation (global host, HTTP, localhost, private IPs, link-local, credentials, empty)
- Image MIME validation (valid image, non-200, non-image content type, network error)
- Storage upload failure with sanitized error messages
- Missing public media URL fails closed in Buffer publishing

#### Verification Evidence

| Command | Result |
|---------|--------|
| `manage.py test content.tests.test_media_storage --keepdb` | PASS, 17 tests |
| `manage.py test content.tests.test_automated_post_orchestration research.tests.ResearchExecutionViewTests --keepdb` | PASS, 22 tests |
| `manage.py test --keepdb --verbosity 1` | PASS, 381 tests (364 original + 17 new) |
| `manage.py check` | PASS, no issues |
| `manage.py makemigrations --check --dry-run` | PASS, no changes detected |
| `compileall -q content research content_automater` | PASS |
| `git diff --check` | PASS |

#### Live Verification Status

**Blocked:** No Cloudflare R2 credentials, bucket, or custom domain are configured in this environment. Live integration verification (upload → retrieve from public HTTPS domain → Buffer auth + destination discovery) cannot be performed until those are provided.

**What remains before live publish:**
1. User creates Cloudflare R2 account, bucket, API credentials, and custom domain
2. User adds R2 env vars to `.env` (never committed)
3. User sets `MEDIA_STORAGE=r2`
4. Owner explicitly authorizes a live Buffer publish to a safe test destination

The workflow specification's “NO mandatory text approval gate” statement conflicts with the existing publishing contract and the authoritative approval requirements. This implementation keeps the current explicit human-approval gate and documents that decision in `AUTOMATED-POST-ORCHESTRATION-IMPLEMENTATION.md`; it does not claim owner approval of a policy change.

---

## Documentation (2026-10-24)

### Learning Guide Created

**Files created:**
- `docs/learning/CODEBASE-LEARNING-GUIDE.md` — Comprehensive beginner-friendly learning guide covering all major subsystems: project overview, repository map, architecture, request/response flows, automated content workflow, database guide, background jobs and Docker, important files explained, code reading lessons, external integrations, testing/debugging, glossary, learning path, troubleshooting reference, and self-assessment with answers.
- `docs/learning/FILE-REFERENCE-MAP.md` — Quick lookup of important files grouped by subsystem, with paths, purposes, key classes/functions, and relationships.

### README Updated

Added a "Learning Guide" section to `README.md` with links to both new documentation files.

### Documentation Gaps Remaining

- No detailed documentation for the `frontend/` and `frontend_ui/` apps beyond what's in the learning guide's file reference map.
- No runbook for production deployment beyond `docker-compose.yml` and `Dockerfile`.
- No troubleshooting guide for Celery worker/beat-specific issues beyond the table in the learning guide.

---

## UX Redesign: Brief-First Social Post Workflow (2026-10-24)

This section documents the brief-first UX redesign implemented per `docs/development/POST-CREATION-UX-REDESIGN-PLAN.md`.

### What changed

The content creation workflow was redesigned from a technical, multi-panel CMS interface to a brief-first social post experience:

**Before:** User fills title/topic/body manually, writes image prompts, picks dimensions, navigates separate version/review/correction/image/publishing panels.

**After:** User enters "What would you like to post?" (short brief), selects connected Buffer channels, and the system auto-generates copy + poster variants. One unified workspace replaces the technical detail page.

### New files

- `docs/development/POST-CREATION-UX-REDESIGN-PLAN.md` — full design plan
- `docs/development/POST-CREATION-UX-REDESIGN-IMPLEMENTATION.md` — implementation status (this section's source)
- `content/services/platform_formats.py` — centralized platform→format mapping
- `content/services/brief_generation_service.py` — brief-based copy generation + review
- `content/tasks/brief_tasks.py` — Celery task chaining text→review→posters
- `content/templates/content/generation_status.html` — Page B generation status
- `content/tests/test_platform_formats.py` — 17 tests
- `content/tests/test_brief_generation.py` — 4 tests
- `content/tests/test_image_variants.py` — 7 tests

### Modified files

- `content/models.py` — Added `brief`, `target_channels`, `generation_status` to `Content`; `platforms`, `generation_state` to `Media`
- `content/migrations/0009_*.py` — Additive migration for Content fields
- `content/migrations/0010_*.py` — Additive migration for Media fields
- `content/services/image_generation_service.py` — Added `generate_poster_variants`, `retry_poster_variant`, `_build_poster_prompt`
- `content/views/__init__.py` — Brief-first create view, generation status view, retry views, unified detail context, dashboard list context
- `content/urls.py` — Added generation_status, generate_retry, retry_poster routes
- `content/templates/content/create.html` — Replaced with brief-first form
- `content/templates/content/detail.html` — Unified workspace (removed `Current Version (v1)` section)
- `content/templates/content/list.html` — Dashboard with status, next action, thumbnail
- `frontend/static/frontend/css/detail.css` — Workspace grid layout

### Preserved (no deletion)

- All version history, `ContentVersion`, `ContentReview`, `PublishingPreparation`, `ContentPublication`, `WorkflowAuditLog`, `Media` records
- All mandatory approval gates: human approval, passing AI review, lifecycle state, channel authorization, public media URL
- Existing research-driven generation path (`ContentGenerationService.generate_draft_for_request`)
- Existing direct platform providers (LinkedIn, Facebook, Twitter)
- Existing Buffer publishing orchestrator with idempotency and partial-failure handling

### Schema changes (additive only, applied)

| Model | Field | Type |
|-------|-------|------|
| Content | brief | TextField(null=True, blank=True) |
| Content | target_channels | JSONField(default=list, blank=True) |
| Content | generation_status | CharField(choices, default='idle') |
| Media | platforms | JSONField(default=list, blank=True) |
| Media | generation_state | CharField(choices, default='pending') |

### Verification

- `manage.py check`: No issues
- `manage.py makemigrations --check --dry-run`: No changes detected
- `manage.py test --keepdb --verbosity 1`: **409 tests, all passing** (381 original + 28 new)
- `git diff --check`: Passed
- No live Buffer or NVIDIA calls made during testing (all mocked)

### Known limitations

- Buffer uses a single shared `BUFFER_ACCESS_TOKEN` (account-level, not per-user OAuth)
- Without Cloudflare R2 public storage, local `/media/` URLs are rejected by Buffer's public-URL check — the UI communicates this clearly
- FLUX image model is not verified to render exact text reliably; no exact-text poster promise
- No live external publishing during implementation

---

## Bug Fix: Brief-First Workflow Reliability (2026-10-25)

This section documents targeted reliability fixes for the brief-first creation workflow, implemented per the bug-fix preset. No redesign was performed.

### Root causes fixed

1. **Invalid Django template filter `|replace`** — `content/templates/content/generation_status.html` used a non-existent `replace` filter, raising `TemplateSyntaxError: Invalid filter: 'replace'` when rendering any generation status containing an underscore (`generating_text`, `generating_posters`, etc.).

2. **Undefined `buffer_status` in create-page validation helper** — `content_create()` computed `buffer_status` in its own scope but called `_handle_brief_create(request, buffer_profiles)` without passing it. On validation failure (empty brief, oversized brief, unauthorized channel), the helper re-rendered `content/create.html` referencing the undefined `buffer_status`, which would raise `NameError`.

3. **Redis/Celery unavailability** — Redis is not installed/running in this environment. The enqueue path in `content_create()` catches exceptions gracefully. **(Updated 2026-10-25: the initial "stay queued" behavior was itself a bug — see the enqueue fix section below.)** No duplicate versions or unsafe publishing result.

### Files changed

| File | Change |
|------|--------|
| `content/views/__init__.py` | Thread `buffer_status` into `_handle_brief_create()`; add `GENERATION_STATUS_LABELS` mapping and `status_label` context variable in `content_generation_status()`. |
| `content/templates/content/generation_status.html` | Replace `{{ content.generation_status\|replace:"_"," "|title }}` with `{{ status_label }}`. CSS class (raw value) preserved. |
| `content/tests/test_views.py` | Add `ContentCreateValidationTest` (empty brief, oversized brief, unauthorized channel, valid-with-no-channels redirect, cross-user 403) and `ContentGenerationStatusTest` (readable labels for underscore statuses, graceful unknown-status, retry button on failed). |
### Verification

- `manage.py check`: No issues
- `manage.py makemigrations --check --dry-run`: No changes detected
- `manage.py test --keepdb --verbosity 1`: **417 tests, all passing** (409 baseline + 8 new regression tests); **423 total after the enqueue-failure fix (+6 tests)**
- `git diff --check`: Passed
- No live Buffer or NVIDIA calls made during testing (all mocked)
- Dev server boots successfully

### Known limitations (this session)

- Redis/Celery runtime end-to-end verification could not be performed (no Redis binaries installed, no Redis process, Docker services not running). Enqueue-failure handling is code-verified and covered by existing behavior; safe command for later: `docker compose up -d redis` (then start worker/beat), or run `redis-server` locally on `localhost:6379` matching `REDIS_URL=redis://localhost:6379/0`.
- Playwright browser verification could not be performed (`playwright` Python package not installed). Equivalent page-rendering behavior is covered by Django test-client regression tests (HTTP 200, readable labels, retry button, validation errors).
- Noted inconsistency (documented, not changed): create-page help text says "at least one destination is required," but drafts may be created with zero channels; publishing requires channels.
- Environment (2026-10-25): the supported project environment is `venv/` (Python 3.12) per `README.md` and `Dockerfile`. Three declared dependencies missing from `venv/` (`gunicorn`, `django-storages`, `boto3`) were installed exactly from the root `requirements.txt`; `pip check` passes. The untracked `.venv/` (Python 3.14, only the first half of `requirements.txt`, Pillow out of declared range) remains unusable and was left untouched. `README.md` references a nonexistent `requirements/development.txt`.

### Bug Fix: Celery Enqueue Failures Left Drafts Unretryable (2026-10-25)

Re-inspection found that the enqueue-failure handling described above contained two real defects. The retry view (`content_generate_retry`) only accepts content in `failed`/`partial`, so the earlier "draft stays in `queued`" behavior made a failed enqueue permanently unretryable.

**Root cause (both paths):**

1. **Initial enqueue failure:** `content_create()` created the draft as `generation_status="queued"`, then called `generate_post_from_brief_task.delay()` in a `try/except` that only logged on failure. The draft stayed `queued` — no working "Try again" button, and the duplicate-submission guard (which reuses recent `idle`/`queued` drafts with the same brief) kept redirecting to the unreachable draft.
2. **Retry enqueue failure:** `content_generate_retry()` persisted `generation_status="queued"` **before** calling `.delay()`. If enqueueing failed, the draft stayed `queued`, so the "Try again" button could never be used again — and the shown error alert contradicted the page's "Queued" status.

**Fix (in `content/views/__init__.py`):**

- Initial enqueue failure → persist `generation_status="failed"` and show `messages.error("Could not start generation. You can try again from the status page.")`. The draft is preserved.
- Retry enqueue failure → restore and persist `generation_status="failed"`; message reworded to "Could not restart generation. Please try again."
- Corrected the stale code comment in `content_create()` and the earlier claim in this section that "the draft persists with status queued and the user can retry."

**Message visibility checked:** Django messages in this app render globally via `frontend/templates/frontend/components/toast_container.html` (included by `frontend/templates/frontend/base.html`), styled with `.alert-success`/`.alert-error` from `frontend/static/frontend/css/components.css`. The regression tests assert the alert text in the rendered response.

**Regression tests (`content/tests/test_views.py`, new `CeleryEnqueueFailureTest`, 6 tests):**

- Initial `.delay()` failure → draft persists with `generation_status="failed"`, error alert rendered.
- Successful initial enqueue → stays `"queued"` (existing behavior intact).
- Retry `.delay()` failure → status returns to `"failed"`.
- Failed retry then successful retry → becomes `"queued"` (recovery path).
- Successful retry → `"queued"` (existing behavior intact).
- Non-owner retry → 403, content unchanged, no task enqueued (authorization intact).

Two pre-existing create tests that asserted `'queued'` after an *unmocked* (i.e., actually failing) enqueue were made hermetic by mocking the task — their assertions now test a genuinely successful enqueue; no assertions were weakened.

**Result:** 423 tests passing (417 earlier + 6 new). Redis availability itself remains out of scope/environments: no Redis binaries, Docker services not running.

### Comprehensive Audit (2026-10-25)

Full runtime, UX, security, and release-readiness audit of the brief-first workflow. Details in `docs/development/BUG-FIX-AND-RUNTIME-VERIFICATION.md` ("Comprehensive audit" section).

**Confirmed defects found and fixed:**

1. **Celery Beat schedule referenced unregistered task names** — `CELERY_BEAT_SCHEDULE` pointed at `content.tasks.schedule_due_campaigns` / `content.tasks.reconcile_ambiguous_publications`, but `@shared_task` registers under the full dotted module path (`content.tasks.campaign_tasks.…` / `content.tasks.publishing_tasks.…`). Beat would never have fired either job. Fixed in `content_automater/settings/base.py`; red-first regression test added (`content/tests/test_celery_config.py`).
2. **Dead `can_publish` block** in `content_detail` (computed then unconditionally overwritten) — removed.
3. **Duplicate status-label mapping** in the status view — now derived from `Content.GENERATION_STATUS_CHOICES` with the unknown-status fallback preserved.
4. **Misleading progress promise** on the status page ("This page updates as each step completes" with no auto-update) — reworded to "Reload this page to see the latest progress."

**Runtime verification performed (live, isolated):** disposable Redis on `127.0.0.1:6379` (removed afterwards) → worker connected and registered all 6 tasks; harmless `debug_task` enqueued and executed end-to-end; broker-down enqueue exception (`OperationalError`) demonstrated. **Beat verified live post-fix:** `schedule-due-campaigns` dispatched by Beat under its corrected registered name and executed by the worker (`{'queued': 0}` — 0 due campaigns verified beforehand); `reconcile_ambiguous_publications` executed as the expected no-op (`{'resolved': 0}`). The real content-generation task was deliberately NOT run against the live worker (would risk live NVIDIA calls). `README.md`'s nonexistent `requirements/development.txt` path was corrected to the root `requirements.txt`.

**Final suite:** **424 tests, 0 failures** (423 + 1 new beat-schedule test). `manage.py check`, `makemigrations --check`, template compilation, `docker compose config`, `git diff --check` all pass.

**Documented, not changed:** ambiguous-publication reconcile is a conservative no-op (no provider implements `check_post_status`); provider error strings stay internal; cosmetic view duplications; dead `frontend_ui` app.

### Final quality gate (2026-10-26) — real browser UX audit

Real-browser verification with the Playwright MCP (no project dependency installed). Full details, evidence tables, and screenshots paths in `docs/development/BUG-FIX-AND-RUNTIME-VERIFICATION.md` ("Final quality gate (2026-10-26)" section).

**New defects found in a real browser and fixed (regression tests added):**

1. **Status-page heading claimed "being prepared" for failed drafts** — now state-aware: failed → "Generation didn't finish", complete → "Your post is ready" (`generation_status.html`; `test_heading_matches_actual_state`, red-first verified).
2. **Brief echo in the failed alert was unlabelled** — now a labelled paragraph "Your brief: …" (`test_failed_alert_labels_the_brief`).
3. **403 denial page rendered in Quirks Mode** (bare string body, no doctype) — now a minimal full HTML document (`content/authorization.py`; `test_forbidden_response_is_a_full_html_document`) plus a new cross-user retry-POST ownership test (`test_unauthorized_user_cannot_retry_generation`).

**Browser flows verified live:** login (email convention), empty/oversized brief client guards, valid brief → real `.delay()` → truthful **Queued** (task confirmed in broker queue), broker-down create → truthful **Failed** with retry controls, retry-failure → still Failed and retryable, retry after broker recovery → **"Generation restarted."** → Queued (no server restart needed), cross-user GET → 403, mobile 390px with no horizontal overflow, console clean (0 errors/warnings).

**Runtime re-verified live (disposable Redis, no worker, provider env emptied):** Redis PONG, worker registry (6 tasks), `debug_task` round-trip, Beat dispatched `schedule-due-campaigns` under its corrected name (`{'queued': 0}`), broker-down `.delay()` → `OperationalError`. No live AI/Buffer call was possible or made; the generation task never executed.

**Final suite: 428 tests, 0 failures.** `manage.py check`, `makemigrations --check`, `docker compose config --quiet`, `git diff --check` all pass.

**Operational notes (documented, not changed):** broker-outage requests block ~20 s in a reconnect loop before failing gracefully (publish path recovers on next attempt — verified); email-login requires the `username == email` registration convention (custom backend would be future work); oversized-brief button disables silently (live character counter would help).
