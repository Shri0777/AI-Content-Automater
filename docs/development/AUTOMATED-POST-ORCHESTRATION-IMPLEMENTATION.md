# Automated Post Orchestration Implementation

**Date:** 2026-10-24  
**Status:** Implemented; Cloudflare R2 storage configured for public HTTPS media URLs. Live Buffer image delivery requires R2 credentials and a custom domain, which are not yet provisioned in this environment.

## Scope and Decision

This increment connects existing campaign research, text generation/review, image generation/storage, and Buffer publishing. It does not introduce a second content-generation or publishing implementation.

The workflow document says campaigns should have no mandatory text approval gate. The authoritative requirements define approval “where manual approval is required,” and the existing publishing contract explicitly requires human approval of the current version. Campaign execution previously stopped at `pending_review`, and both publishing preparation and the Buffer orchestrator reject unapproved versions. The implementation preserves that contract: AI review and bounded correction run automatically; image generation follows a passing AI review; Buffer submission cannot occur until the current text version has explicit human approval and image approval has passed when configured. No automatic text approval is performed.

When a campaign has `publish_immediately=False`, the workflow performs the existing final validation after approvals and stops at `ready_to_publish`. When enabled, Buffer submission is attempted only after that same validation and the existing destination checks.

## Implementation

### Research and text

- `ResearchCollectionService` contains the existing supported RSS/GNews collection, ranking, and persistence logic. `research.views.request_execute` delegates to it, and campaign execution invokes the same service.
- `ContentGenerationService.generate_draft_for_request` generates a version and performs mandatory AI review stage 1.
- `ContentCorrectionService.apply_bounded_correction` performs the existing bounded revisions and stage 2 reviews. Campaign execution allows at most two correction attempts and stops before image generation unless the latest review passes.
- No new source categories, provider behavior, or alternate review implementation were added.

### Image and approval

- `AutomatedPostOrchestrationService.build_image_prompt` uses up to the first 720 characters of the reviewed final version as the image brief.
- `ImageGenerationService` persists media through the existing Django storage path. The orchestrator verifies owner, content association, validation status, and image MIME type before attaching the media to `CampaignExecution`.
- `Campaign.image_approval_required` defaults to true. `Media.approval_status`, `reviewed_by`, and `reviewed_at` persist the approval decision. Approval and rejection are owner-scoped POST routes protected by Django CSRF middleware.
- Pending or rejected images cannot advance to Buffer. Rejection is terminal for that generated image; this increment does not silently regenerate a replacement.
- The exact text version used for image generation is recorded in execution data. If text changes during image generation or before publishing, that image is invalidated/refused; a new campaign execution is needed for a new image.
- Image provider/storage failures use sanitized user-facing messages and logs expose only the error category/type, not raw provider or storage exception text.

### Final validation and Buffer

- `submit_to_buffer_task` checks current-version human approval, configured image approval, and a passing review before using `PublishingPreparationService` for final validation. The shared `BufferPublishingOrchestrator` also enforces campaign image presence/approval and an existing prepared validation record, so manual and automatic publishing cannot bypass the same checks.
- Campaign `target_platforms` is used as the requested Buffer destination ID list. IDs are checked against live verified Buffer profiles before final validation and again by the existing publishing orchestrator before dispatch.
- With automatic submission enabled, the existing `BufferPublishingOrchestrator` receives the image URL and stable idempotency key `campaign-execution-{execution_id}`. Existing per-channel publication keys and ambiguous-state handling remain authoritative.
- Buffer GraphQL receives text and an image asset URL. URL checks require HTTPS, globally routable DNS results, an anonymous HEAD response with status 200, and an `image/*` content type. Redirects are rejected. The URL is not written into application logs or publication response data.
- Buffer requests are non-idempotent. Ambiguous results remain ambiguous and are not retried by the new task. Existing bounded low-level retry behavior is preserved for its safe transient cases.

## Schema

Migration: `content/migrations/0008_campaign_image_approval_required_and_more.py`.

- Adds `Campaign.image_approval_required` (default true).
- Adds nullable unique `CampaignExecution.execution_key` and optional `image_media` reference.
- Adds media approval status and reviewer audit fields.

The migration is additive. Test setup applied it to the existing test database; no development/production `migrate` command was run. No database was dropped or recreated.

## Retry and Failure Behavior

- Celery execution retries reuse an execution key derived from the Celery task ID; scheduled work uses a campaign-and-due-time key. A database uniqueness constraint prevents a second execution row for the same key.
- An execution row lock and 15-minute active-run guard prevent concurrent duplicate work. An execution that completed with media returns as a duplicate without generating or submitting again. The lease allows recovery if an execution worker disappears; explicit Celery retries can resume immediately.
- Content and research-request association writes are performed in transactions. Campaign success/failure counters are incremented once using an execution-data marker and database `F()` updates.
- Image-generation exceptions are retried by the campaign task at most twice. A terminal failure is recorded with a sanitized message and error type.
- Buffer submission uses the existing durable publication records. Ambiguous statuses are preserved and never blindly retried by the new task.
- Research collection persistence is transactional and avoids duplicate canonical URLs for the same request.

## Configuration and Limitations

- **Local development:** `MEDIA_URL='/media/'`, local filesystem storage. Not publicly reachable HTTPS. Buffer image publishing fails closed.
- **Production with R2:** When `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_DOMAIN`, and `MEDIA_STORAGE=r2` are all set, Django uses `storages.backends.s3boto3.S3Boto3Storage` backed by Cloudflare R2. `MEDIA_URL` becomes `https://<R2_PUBLIC_DOMAIN>/`, providing stable, publicly reachable HTTPS URLs for Buffer image publishing.
- The R2 bucket is **private**. Public access is via the custom domain only (`AWS_QUERYSTRING_AUTH=False`, `AWS_DEFAULT_ACL=None`). No signed URLs or public bucket ACLs are used.
- `Campaign.target_platforms` must contain verified Buffer channel IDs for the new pipeline. The campaign form accepts comma-separated IDs, and the server verifies them before use. Existing campaigns with an empty target list will stop before submission with a missing-destination result.
- `publish_immediately=False` only prepares a validated post; it does not create a Buffer post.
- The workflow spec's text-approval statement remains a documentary conflict. This implementation follows the current publication contract and authoritative requirements. A future owner decision would be required to change that contract; none is inferred here.
- No live AI image API call, Buffer publish, destination mutation, or paid external call was performed as part of the new tests. The local media/CDN reachability path was not integration-tested against a real public storage host. Live verification requires R2 credentials and Buffer credentials.

## Verification Evidence

Commands run against the existing local virtual environment:

| Command | Result |
|---|---|
| `env PYTHONPYCACHEPREFIX=/tmp/ai-automater-pycache venv/bin/python manage.py check` | PASS, no issues |
| `env PYTHONPYCACHEPREFIX=/tmp/ai-automater-pycache venv/bin/python manage.py makemigrations --check --dry-run` | PASS, no changes detected |
| `env PYTHONPYCACHEPREFIX=/tmp/ai-automater-pycache venv/bin/python manage.py test content.tests.test_media_storage --keepdb --verbosity 1` | PASS, 17 tests |
| `env PYTHONPYCACHEPREFIX=/tmp/ai-automater-pycache venv/bin/python manage.py test content.tests.test_automated_post_orchestration research.tests.ResearchExecutionViewTests --keepdb --verbosity 1` | PASS, 22 tests |
| `env PYTHONPYCACHEPREFIX=/tmp/ai-automater-pycache venv/bin/python manage.py test --keepdb --verbosity 1` | PASS, 381 tests in 72.316 seconds |
| `env PYTHONPYCACHEPREFIX=/tmp/ai-automater-pycache venv/bin/python -m compileall -q content research content_automater` | PASS |
| `git diff --check` | PASS |

The focused suite covers storage backend configuration, missing/malformed R2 config, HTTPS and image MIME validation, private-address and redirect rejection, storage upload failure, image URL delivery to Buffer payload, approval and final-validation enforcement, idempotency, and ambiguous Buffer outcomes. New external API paths are mocked. Existing research-execution regression tests also pass.

The full suite emitted pre-existing expected warnings for absent collected static assets and negative-path requests, but had no test failures.

## Changed Files

- `content/models.py`, `content/migrations/0008_campaign_image_approval_required_and_more.py`
- `content/services/automated_post_orchestration.py`
- `content/services/buffer_service.py`, `content/services/publishing_orchestrator.py`
- `content/services/image_generation_service.py`
- `content/tasks/campaign_tasks.py`, `content/tasks/__init__.py`
- `content/tests/test_automated_post_orchestration.py`
- `content/tests/test_media_storage.py` (NEW)
- `content/views/campaign_views.py`, `content/views/__init__.py`, `content/urls.py`
- `content/templates/content/campaigns/create.html`, `content/templates/content/campaigns/detail.html`
- `research/services/collection_service.py`, `research/views.py`
- `content_automater/settings/base.py` (R2 storage configuration)
- `.env.example` (R2 placeholder env vars)
- `requirements.txt` (added `django-storages`, `boto3`)
- `docs/development/IMPLEMENTATION-PROGRESS.md`
- `docs/development/AUTOMATED-POST-ORCHESTRATION-IMPLEMENTATION.md`

No dependency or secret configuration changed beyond adding `django-storages` and `boto3` to requirements. No files were staged or committed.
