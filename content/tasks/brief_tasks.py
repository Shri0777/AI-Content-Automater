"""
Celery tasks for the brief-first generation workflow.

Tasks are designed to be called directly in tests (no worker required) and
enqueued via `.delay()` / `.apply_async()` in production.
"""

import logging

from celery import shared_task

from content.models import Content

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_post_from_brief_task(self, content_id: int) -> dict:
    """
    Generate post copy from a persisted brief, then run quality review and
    generate poster variants for the selected destinations.

    Args:
        content_id: PK of the Content record to generate for.

    Returns:
        Dict with 'success' plus result details, or 'error' / 'error_type'.
    """
    try:
        content = Content.objects.get(pk=content_id)
    except Content.DoesNotExist:
        logger.error("Content %s not found for brief generation.", content_id)
        return {"success": False, "error": "Content draft not found.", "error_type": "not_found"}

    from content.services.brief_generation_service import BriefGenerationService
    from content.services.image_generation_service import ImageGenerationService

    # ── Step 1: Generate copy and run quality review ──
    content.generation_status = "generating_text"
    content.save(update_fields=["generation_status", "updated_at"])

    try:
        gen_result = BriefGenerationService.generate_post_from_brief(
            content=content, user=content.owner
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Brief generation task failed for content %s", content_id)
        content.generation_status = "failed"
        content.save(update_fields=["generation_status", "updated_at"])
        return {
            "success": False,
            "error": "An unexpected error occurred during generation.",
            "error_type": "unexpected_error",
        }

    if not gen_result.get("success", False):
        return gen_result

    # ── Step 2: Generate poster variants for selected destinations ──
    content.generation_status = "generating_posters"
    content.save(update_fields=["generation_status", "updated_at"])

    destinations = _resolve_destinations(content)
    copy = (content.current_version.content_text or "").strip() if content.current_version else ""
    brand_context = content.description or None

    try:
        poster_result = ImageGenerationService.generate_poster_variants(
            content=content,
            user=content.owner,
            brief=(content.brief or ""),
            copy=copy,
            destinations=destinations,
            brand_context=brand_context,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Poster generation failed for content %s", content_id)
        content.generation_status = "failed"
        content.save(update_fields=["generation_status", "updated_at"])
        return {
            "success": False,
            "error": "Poster generation failed.",
            "error_type": "unexpected_error",
        }

    # ── Step 3: Final status ──
    if poster_result.get("success", False):
        if poster_result.get("successful_count", 0) < poster_result.get("total", 0):
            content.generation_status = "partial"
        else:
            content.generation_status = "complete"
    else:
        content.generation_status = "failed"

    content.save(update_fields=["generation_status", "updated_at"])

    return {
        "success": True,
        "content": content,
        "version": gen_result.get("version"),
        "review": gen_result.get("review"),
        "posters": poster_result,
    }


def _resolve_destinations(content: Content) -> list:
    """
    Resolve the content's target channel IDs into destination dicts with
    service names, by querying the configured Buffer account.

    If Buffer is unavailable or unconfigured, falls back to square format
    for every channel ID so poster generation still proceeds.
    """
    channel_ids = content.target_channels or []
    if not channel_ids:
        return []

    try:
        from content.services.buffer_service import BufferPublishingService
        buffer_service = BufferPublishingService()
        profiles = buffer_service.get_profiles()
    except Exception:
        logger.warning("Could not fetch Buffer profiles for content %s; using square fallback.", content.pk)
        return [{"id": cid, "service": "unknown"} for cid in channel_ids]

    id_to_service = {str(p.get("id")): p.get("service", "unknown") for p in profiles if p.get("id")}
    return [
        {"id": cid, "service": id_to_service.get(cid, "unknown")}
        for cid in channel_ids
    ]
