# AI Content Automater — File Reference Map

**Purpose:** Quick lookup of important files, their purposes, and relationships.  
**Repository:** `/home/shri/Development/AI-AUTOMATER`

Use this alongside `CODEBASE-LEARNING-GUIDE.md` for detailed explanations.

---

## How to use this map

1. Find the subsystem you're interested in (e.g., "Buffer publishing", "Database models").
2. Read the "Purpose" and "Key classes/functions" columns.
3. Use the "Path" to open the file.
4. Follow "Depends on" / "Called by" to trace relationships.

---

## 1. Project Configuration

| Path | Purpose | Key items | Called by / Depends on |
|------|---------|-----------|------------------------|
| `manage.py` | Django CLI entry point | `main()` | Run directly: `python manage.py ...` |
| `content_automater/settings/base.py` | Shared Django settings (all environments) | `DATABASES`, `INSTALLED_APPS`, `CELERY_*`, `MEDIA_*`, `BUFFER_*`, `R2_*`, `TEXT_*`, `IMAGE_*` | `development.py`, `production.py`, `manage.py` |
| `content_automater/settings/development.py` | Development overrides | `DEBUG=True`, `ALLOWED_HOSTS`, `EMAIL_BACKEND` | `manage.py` (default) |
| `content_automater/settings/production.py` | Production overrides | Required `SECRET_KEY`, `ALLOWED_HOSTS`, secure cookies | `DJANGO_SETTINGS_MODULE=content_automater.settings.production` |
| `content_automater/urls.py` | Root URL routing | `urlpatterns` including `content/`, `research/`, `auth/`, `ai/`, `admin/` | Django URL resolver |
| `content_automater/celery.py` | Celery app configuration | `app`, `autodiscover_tasks()`, `debug_task` | Celery worker/beat |
| `content_automater/wsgi.py` | WSGI application | `application` | Gunicorn, web servers |
| `content_automater/asgi.py` | ASGI application | `application` | ASGI servers |
| `requirements.txt` | Python dependencies | All pip packages | `pip install -r requirements.txt` |
| `.env.example` | Example environment variables (placeholders only) | All `*_KEY`, `*_URL`, `*_ID`, `*_DOMAIN` vars | Copy to `.env` for local dev |
| `.env` | Local environment variables (gitignored) | Actual local values | Loaded by `python-dotenv` in base.py |
| `docker-compose.yml` | Multi-service Docker orchestration | `db`, `redis`, `web`, `worker`, `beat` services | `docker compose up/down` |
| `Dockerfile` | Container image build | Python 3.12, dependencies, non-root user | `docker compose build` |

---

## 2. Content App (Core Business Logic)

### Models

| Path | Purpose | Key classes | Depends on |
|------|---------|-------------|------------|
| `content/models.py` | All database models | `Content`, `ContentVersion`, `ContentReview`, `PublishingPreparation`, `WorkflowAuditLog`, `ContentPublication`, `Campaign`, `CampaignExecution`, `Media`, `Notification`, `PublicationMetrics` | Django `models`, `User` |

### Views

| Path | Purpose | Key functions | Called by |
|------|---------|---------------|-----------|
| `content/views/__init__.py` | Content HTTP handlers | `content_list`, `content_create`, `content_detail`, `content_edit`, `content_trigger_review`, `content_apply_correction`, `content_approve_version`, `content_prepare_publishing`, `content_transition`, `content_publish`, `content_reconcile_publication` | URL routing, templates |
| `content/views/campaign_views.py` | Campaign HTTP handlers | `campaign_list`, `campaign_detail`, `campaign_create`, `campaign_activate`, `campaign_pause`, `campaign_execute_now`, `campaign_delete`, `campaign_image_approve`, `campaign_image_reject` | URL routing, templates |

### URL routing

| Path | Purpose | Key items |
|------|---------|-----------|
| `content/urls.py` | Content app URL patterns | `app_name='content'`, paths for content CRUD, campaigns, media, notifications, analytics |

### Services (business logic)

| Path | Purpose | Key classes/methods | Called by |
|------|---------|---------------------|-----------|
| `content/services/__init__.py` | Services package exports | `ContentGenerationService`, `QualityReviewService`, `ContentCorrectionService`, `PublishingPreparationService`, `WorkflowOrchestratorService`, `BufferPublishingService`, `BufferPublishingOrchestrator` | Views, tasks, other services |
| `content/services/generation_service.py` | AI text generation | `ContentGenerationService.generate_draft_for_request()` | Views, campaign tasks |
| `content/services/review_service.py` | AI quality review | `QualityReviewService.review_version()` | Views, campaign tasks |
| `content/services/correction_service.py` | Bounded AI correction | `ContentCorrectionService.apply_bounded_correction()` | Views, campaign tasks |
| `content/services/publishing_service.py` | Final validation before publishing | `PublishingPreparationService.prepare_content()`, `invalidate_preparations_for_content()` | Views, orchestration |
| `content/services/workflow_orchestrator.py` | Workflow state transitions | `WorkflowOrchestratorService.approve_content_version()`, `prepare_content_for_publishing()`, `execute_state_transition()` | Views |
| `content/services/buffer_service.py` | Buffer GraphQL API client | `BufferPublishingService.get_connection_status()`, `get_profiles()`, `create_update()`, `_is_public_https_url()`, `_is_reachable_image_url()` | Publishing orchestrator, views |
| `content/services/publishing_orchestrator.py` | Buffer publishing coordination | `BufferPublishingOrchestrator.execute_publishing()`, `reconcile_publication()` | Views, campaign tasks |
| `content/services/image_generation_service.py` | AI image generation + media storage | `ImageGenerationService.generate_image_for_content()`, `validate_image_prompt()` | Orchestration service, views |
| `content/services/automated_post_orchestration.py` | Campaign image + Buffer pipeline | `AutomatedPostOrchestrationService.generate_image()`, `submit_to_buffer()` | Campaign tasks |
| `content/services/media_service.py` | Media file management | — | Views |
| `content/services/notification_service.py` | User notifications | `NotificationService.create_notification()` | Campaign tasks, views |

### Tasks (Celery background jobs)

| Path | Purpose | Key tasks | Called by |
|------|---------|-----------|-----------|
| `content/tasks/__init__.py` | Tasks package init | — | Celery autodiscovery |
| `content/tasks/campaign_tasks.py` | Campaign pipeline tasks | `execute_campaign_task`, `submit_to_buffer_task`, `schedule_due_campaigns`, `_schedule_next_execution` | Celery Beat, views, other tasks |

### Forms and authorization

| Path | Purpose | Key items |
|------|---------|-----------|
| `content/forms.py` | Django forms for content creation/editing | `ContentForm`, `ContentVersionForm` |
| `content/authorization.py` | Ownership checks | `user_owns_content` decorator |

### Admin

| Path | Purpose |
|------|---------|
| `content/admin.py` | Django admin registration for content models |

### Templates

| Path | Purpose |
|------|---------|
| `content/templates/content/` | HTML templates for content, campaigns, media, notifications |

---

## 3. Research App

| Path | Purpose | Key classes | Depends on |
|------|---------|-------------|------------|
| `research/models.py` | Research data models | `ResearchProfile`, `ContentCreationRequest`, `Research`, `ResearchContentAssociation` | `content.Content`, Django `User` |
| `research/views.py` | Research HTTP handlers | `request_execute` (delegates to `ResearchCollectionService`) | URL routing |
| `research/services/collection_service.py` | Research collection logic | `ResearchCollectionService.collect()` | Views, campaign tasks |
| `research/urls.py` | Research URL patterns | — | URL routing |
| `research/admin.py` | Django admin registration | — | — |

---

## 4. AI Providers App

| Path | Purpose | Key classes | Depends on |
|------|---------|-------------|------------|
| `ai_providers/services/base_adapter.py` | Abstract adapter interface | `BaseProviderAdapter`, `ProviderCapability`, `AuthMethod`, `ProviderErrorType`, `GenerationRequest`, `GenerationResult` | All provider adapters |
| `ai_providers/services/registry.py` | Provider registry (singleton) | `ProviderRegistry`, `registry` | `validation_service.py`, adapters |
| `ai_providers/services/validation_service.py` | Credential validation + provider resolution | `CredentialValidationService.validate_and_save()`, `get_active_provider_for_user()` | Services, adapters |
| `ai_providers/services/security.py` | Endpoint SSRF protection | `validate_safe_endpoint()` | `validation_service.py` |
| `ai_providers/services/openai_adapter.py` | OpenAI text generation | `OpenAIAdapter` | `BaseProviderAdapter` |
| `ai_providers/services/anthropic_adapter.py` | Anthropic text generation | `AnthropicAdapter` | `BaseProviderAdapter` |
| `ai_providers/services/nvidia_adapter.py` | NVIDIA text generation | `NVIDIAAdapter` | `BaseProviderAdapter` |
| `ai_providers/services/nvidia_flux_adapter.py` | NVIDIA FLUX image generation | `NVIDIAFluxAdapter` | `BaseProviderAdapter` |
| `ai_providers/models.py` | Provider config + encrypted credentials | `ProviderConfig`, `ProviderCredential` | `validation_service.py` |
| `ai_providers/views.py` | Provider management views | — | URL routing |
| `ai_providers/urls.py` | AI provider URL patterns | — | URL routing |

---

## 5. Users App

| Path | Purpose | Key items |
|------|---------|-----------|
| `users/models.py` | User model (if custom) | — |
| `users/views.py` | Authentication views | Login, registration, password reset |
| `users/forms.py` | Auth forms | — |
| `users/urls.py` | Auth URL patterns | — |
| `users/admin.py` | Django admin registration | — |

---

## 6. Frontend Apps

| Path | Purpose | Key items |
|------|---------|-----------|
| `frontend/views.py` | Dashboard, navigation views | Dashboard rendering |
| `frontend/urls.py` | Frontend URL patterns | Root route `""` |
| `frontend_ui/models.py` | Frontend UI data models | — |
| `frontend_ui/views.py` | Frontend UI views | — |
| `frontend_ui/urls.py` | Frontend UI URL patterns | — |

---

## 7. Tests

| Path | Purpose | Key test classes |
|------|---------|------------------|
| `content/tests/test_media_storage.py` | R2 storage config + Buffer URL validation tests | `R2StorageConfigurationTests`, `BufferImageURLValidationTests`, `BufferReachableImageValidationTests`, `StorageUploadFailureTests`, `StorageMissingConfigTests` |
| `content/tests/test_automated_post_orchestration.py` | Campaign orchestration tests | `AutomatedPostOrchestrationTests`, `CampaignTaskIdempotencyTests` |
| `content/tests/test_models.py` | Model tests | — |
| `content/tests/test_views.py` | View tests | — |
| `content/tests/test_phase4.py` | Phase 4 tests | — |
| `content/tests/test_phase5.py` | Phase 5 tests | — |
| `content/tests/test_phase6.py` | Phase 6 (Buffer) tests | — |
| `content/tests/test_image_generation_views.py` | Image generation view tests | — |
| `content/tests/test_new_features.py` | New feature tests | — |
| `content/tests/test_social_providers.py` | Social provider tests | — |
| `research/tests.py` | Research tests | — |
| `research/test_views.py` | Research view tests | — |

---

## 8. Migrations

| Path | Purpose |
|------|---------|
| `content/migrations/0001_initial.py` through `0008_*` | Content app schema changes |
| `content/migrations/0008_campaign_image_approval_required_and_more.py` | Adds `image_approval_required`, `execution_key`, `image_media`, media approval fields |
| `research/migrations/` | Research app schema changes |
| `ai_providers/migrations/` | AI providers schema changes |
| `users/migrations/` | Users app schema changes |

---

## 9. Documentation

| Path | Purpose |
|------|---------|
| `README.md` | Project overview, setup, features |
| `docs/learning/CODEBASE-LEARNING-GUIDE.md` | Comprehensive beginner-friendly learning guide (this guide's companion) |
| `docs/learning/FILE-REFERENCE-MAP.md` | This file |
| `docs/development/IMPLEMENTATION-PROGRESS.md` | Implementation progress tracking |
| `docs/development/AUTOMATED-POST-ORCHESTRATION-IMPLEMENTATION.md` | Automated post orchestration spec |
| `docs/development/CONTENT-TO-IMAGE-TO-BUFFER-WORKFLOW.md` | Content-to-image-to-buffer workflow design |
| `docs/development/*.md` | Various phase reports, requirements, design documents |

---

## 10. Quick Relationship Lookup

### "I need to understand how publishing works"
Read in order:
1. `content/services/publishing_service.py` — final validation gates
2. `content/services/buffer_service.py` — Buffer API client
3. `content/services/publishing_orchestrator.py` — publishing coordination
4. `content/services/automated_post_orchestration.py` — campaign pipeline
5. `content/models.py` — `ContentPublication`, `PublishingPreparation`

### "I need to understand how AI generation works"
Read in order:
1. `ai_providers/services/base_adapter.py` — adapter interface
2. `ai_providers/services/registry.py` — provider registry
3. `ai_providers/services/validation_service.py` — credential resolution
4. `content/services/generation_service.py` — text generation
5. `content/services/image_generation_service.py` — image generation

### "I need to understand how campaigns work"
Read in order:
1. `content/models.py` — `Campaign`, `CampaignExecution`
2. `content/tasks/campaign_tasks.py` — Celery tasks
3. `content/services/automated_post_orchestration.py` — pipeline service
4. `content/views/campaign_views.py` — campaign views

### "I need to understand the database"
Read in order:
1. `content/models.py` — all model definitions
2. `content/migrations/0008_campaign_image_approval_required_and_more.py` — example migration
3. Run `python manage.py showmigrations` to see migration status

### "I need to understand configuration"
Read in order:
1. `content_automater/settings/base.py` — all settings
2. `.env.example` — required environment variables
3. `docker-compose.yml` — Docker service configuration
4. `Dockerfile` — container build

---

## 11. File Types Legend

| Type | Description |
|------|-------------|
| **Models** | Database table definitions (`models.py`) |
| **Views** | HTTP request handlers (`views/`, `views/__init__.py`) |
| **Services** | Business logic layer (`services/`) |
| **Tasks** | Celery background jobs (`tasks/`) |
| **URLs** | URL routing (`urls.py`) |
| **Forms** | Django form validation (`forms.py`) |
| **Templates** | HTML templates (`templates/`) |
| **Migrations** | Database schema changes (`migrations/`) |
| **Tests** | Test suite (`tests/`) |
| **Config** | Project settings (`settings/`, `.env*`, `docker-compose.yml`, `Dockerfile`) |

---

## Verification

All file paths, class names, function names, and relationships listed in this map were verified against the actual repository at `/home/shri/Development/AI-AUTOMATER`. No application code was modified to create this document.

For detailed explanations of each file's purpose, inputs, outputs, dependencies, and failure modes, see `docs/learning/CODEBASE-LEARNING-GUIDE.md` Section H ("Important Files Explained").