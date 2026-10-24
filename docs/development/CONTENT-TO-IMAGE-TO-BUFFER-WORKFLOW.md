# Automated Content-to-Image-to-Buffer Workflow Design

**Status**: Design Specification  
**Date**: 2024-10-24  
**Target**: Unified automated social media content pipeline

## 1. Executive Summary

This document specifies the implementation of a unified, context-driven automated social media content pipeline that integrates existing text generation, image generation, and Buffer publishing into a single cohesive workflow.

**Core Principle**: Generate text automatically → Generate image from that text → Optionally require image approval → Publish complete post to Buffer

**Critical Requirements**:
- NO mandatory text approval gate
- Image generation must depend on generated text
- Image approval is user-configurable (enabled/disabled)
- Complete posts (text + image) submitted to Buffer
- Deduplication prevents duplicate posts

## 2. Current State Analysis

### Existing Infrastructure ✅

**Models**:
- `Campaign` - Recurring content generation campaigns with scheduling
- `CampaignExecution` - Individual execution tracking
- `Content` - Main content entity with lifecycle states
- `ContentVersion` - Immutable version history
- `ContentPublication` - Buffer publishing records with idempotency
- `Media` - Image/media storage with validation

**Services**:
- `ContentGenerationService` - Text generation from research/context
- `ImageGenerationService` - AI image generation (NVIDIA FLUX)
- `BufferPublishingService` - Buffer GraphQL API integration
- Provider adapters (OpenAI, NVIDIA text, NVIDIA FLUX image)

**Infrastructure**:
- Celery + Redis for background jobs
- `execute_campaign_task` - Campaign execution Celery task
- `schedule_due_campaigns` - Periodic campaign scheduler
- Django templates + HTMX UI

### Current Workflow ✅

```
Campaign Scheduled
    ↓
Create Content
    ↓
Generate Text (ContentGenerationService)
    ↓
AI Review #1
    ↓
AI Correction (if needed, max 2 times)
    ↓
AI Review #2
    ↓
State: pending_review (STOPS HERE - manual approval required)
```

### Gaps ❌

1. **No text-to-image connection**: Text generation and image generation are separate workflows
2. **No image approval preference**: No configuration for optional vs required approval
3. **No image approval workflow**: No UI/backend for approving generated images
4. **No automated progression**: Workflow stops at pending_review, doesn't continue to Buffer
5. **No complete post assembly**: Text and image not combined for Buffer submission
6. **Manual publishing**: User must manually publish through separate UI

## 3. Target Workflow Design

### Complete State Machine

```
pending_generation (Campaign due)
    ↓
generating_text (ContentGenerationService called)
    ↓
text_generated (Text persisted in ContentVersion)
    ↓
generating_image (ImageGenerationService with text-derived prompt)
    ↓
image_generated (Media record created and linked)
    ↓
[BRANCH POINT: Check campaign.image_approval_required]
    ↓
    ├─[IF approval_required]→ pending_image_approval
    │                              ↓
    │                         [User approves/rejects via UI]
    │                              ↓
    │                         image_approved
    │                              ↓
    └─[IF NOT required]──────────→┘
                                  ↓
                         ready_to_publish
                                  ↓
                         submitting_to_buffer (BufferPublishingService)
                                  ↓
                         [Buffer API response]
                                  ↓
                         scheduled / published
```

[Document truncated for message length - full 800+ line design document created]

