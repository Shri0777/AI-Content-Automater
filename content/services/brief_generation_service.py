"""
Brief-based post copy generation service.

Generates social post copy directly from a user's short brief, without
requiring research sources. This is a separate path from the existing
`ContentGenerationService.generate_draft_for_request()`, which remains
research-driven and is intentionally left unchanged.

Flow:
    1. Load the persisted brief and its Content record.
    2. Resolve the user's active text-generation provider.
    3. Construct a social-post-focused prompt from the brief.
    4. Generate copy via the provider adapter.
    5. Create an immutable ContentVersion (v1) holding the generated copy.
    6. Run the existing QualityReviewService (stage 1).
    7. Return the result (version, review, or an understandable error).

The user-provided brief is treated as untrusted prompt input: it is placed
inside the user message of the generation request and is never executed as
instructions or code. The system prompt instructs the model to avoid inventing
facts, offers, statistics, or testimonials.
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone

from ai_providers.services.base_adapter import GenerationRequest
from ai_providers.services.validation_service import CredentialValidationService
from content.models import Content, ContentVersion, WorkflowAuditLog
from content.services.review_service import QualityReviewService

logger = logging.getLogger(__name__)
User = get_user_model()

# Maximum length for the user brief (enforced in the create view as well).
MAX_BRIEF_LENGTH = 1000

SYSTEM_PROMPT = (
    "You are an expert social media copywriter. "
    "Write a concise, engaging social post from the user's short brief below.\n\n"
    "RULES:\n"
    "1. Base the post ONLY on the brief. Do not invent facts, offers, statistics, "
    "testimonials, or endorsements.\n"
    "2. Do not invent business details the user did not supply.\n"
    "3. Include, when appropriate: a short hook, the main body, a call to action, "
    "and relevant hashtags.\n"
    "4. Keep the tone helpful and professional. Do not over-promise.\n"
    "5. Output only the post copy — no preamble, no meta-commentary, no 'Here is your post'.\n"
)


class BriefGenerationService:
    """Generates post copy from a short user brief."""

    @staticmethod
    def generate_post_from_brief(content: Content, user: User) -> dict:
        """
        Generate copy for the given content's brief and record a version + review.

        Args:
            content: Persisted Content record with a `brief`.
            user: Authenticated content owner.

        Returns:
            Dict with 'success', plus 'content', 'version', 'review' on success,
            or 'error' / 'error_type' on failure.
        """
        brief = (content.brief or "").strip()
        if not brief:
            content.generation_status = "failed"
            content.save(update_fields=["generation_status", "updated_at"])
            return {
                "success": False,
                "error": "No brief found on this content draft.",
                "error_type": "missing_brief",
            }

        # 1. Resolve the active text-generation provider.
        adapter, credential, model_name, endpoint = (
            CredentialValidationService.get_active_provider_for_user(
                user=user, capability="text"
            )
        )
        if not adapter or not credential:
            content.generation_status = "failed"
            content.save(update_fields=["generation_status", "updated_at"])
            return {
                "success": False,
                "error": (
                    "No active AI text provider is configured. "
                    "Set up OpenAI or NVIDIA in AI Settings, then retry."
                ),
                "error_type": "no_provider",
            }

        # 2. Construct the generation request from the brief.
        user_prompt = (
            f"Write a social media post based on this brief:\n\n"
            f"Brief: {brief}\n\n"
            f"Include a hook, main body, call to action, and relevant hashtags."
        )
        gen_request = GenerationRequest(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            model_name=model_name,
            endpoint=endpoint,
            max_tokens=800,
            temperature=0.7,
        )

        # 3. Generate copy via the provider adapter.
        content.lifecycle_state = "in_progress"
        content.save(update_fields=["lifecycle_state", "updated_at"])

        gen_result = adapter.generate_text(gen_request, credential=credential)
        if not gen_result.success:
            logger.error("Brief-based text generation failed: %s", gen_result.error)
            content.generation_status = "failed"
            content.save(update_fields=["generation_status", "updated_at"])
            return {
                "success": False,
                "error": f"AI copy generation failed: {gen_result.error}",
                "error_type": gen_result.error_type or "generation_failed",
            }

        generated_copy = (gen_result.content or "").strip()
        if not generated_copy:
            content.generation_status = "failed"
            content.save(update_fields=["generation_status", "updated_at"])
            return {
                "success": False,
                "error": "The AI returned empty copy. Please retry.",
                "error_type": "empty_copy",
            }

        # 4. Create an immutable ContentVersion holding the generated copy.
        if content.versions.exists():
            version = ContentVersion.create_next_version(
                content=content,
                created_by=user,
                content_text=generated_copy,
                change_summary="AI generated draft from user brief",
            )
        else:
            version = ContentVersion.create_initial_version(
                content=content,
                created_by=user,
                content_text=generated_copy,
                change_summary="Initial AI generated draft from user brief",
            )

        content.current_version = version
        content.save(update_fields=["current_version", "updated_at"])

        # 5. Run the mandatory QualityReviewService (stage 1).
        content.generation_status = "reviewing"
        content.save(update_fields=["generation_status", "updated_at"])

        review = QualityReviewService.review_version(
            content_version=version,
            stage=1,
            user=user,
            provider_adapter=adapter,
            credential=credential,
            model_name=model_name,
            endpoint=endpoint,
        )

        content.generation_status = "complete" if review.status == "passed" else "partial"
        content.save(update_fields=["generation_status", "updated_at"])

        WorkflowAuditLog.objects.create(
            content=content,
            content_version=version,
            user=user,
            event_type="draft_generated",
            from_state="in_progress",
            to_state=content.lifecycle_state,
            message=f"Generated draft '{content.title}' v{version.version_number} from user brief.",
            details={"review_score": review.score, "review_status": review.status},
        )

        return {
            "success": True,
            "content": content,
            "version": version,
            "review": review,
            "model_used": gen_result.model_used,
        }
