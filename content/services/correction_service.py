"""
Bounded automated content correction service for AI Content Automater V2 (Phase 4).

Implements FR-008 (AI Correction), FR-009 (AI Review Stage 2), and FR-010 (Finite Revision Limit).
Enforces bounded revisions (max 2), version immutability, and approval invalidation.
"""
import logging
from typing import Any, Dict, Optional

from ai_providers.services.base_adapter import GenerationRequest
from ai_providers.services.validation_service import CredentialValidationService
from content.models import Content, ContentReview, ContentVersion
from research.models import ResearchContentAssociation

from .review_service import QualityReviewService

logger = logging.getLogger(__name__)

# FR-010: Strict finite automated revision limit
MAX_AUTOMATED_REVISIONS = 2


class ContentCorrectionService:
    """
    Applies bounded automated revisions to content versions based on review critique.
    """
    
    @staticmethod
    def apply_bounded_correction(
        content_id: int,
        user: Any,
        user_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute bounded correction on the current content version.
        
        Args:
            content_id: PK of Content to correct
            user: Authenticated user (ownership verified)
            user_notes: Optional user-specified correction instructions
            
        Returns:
            Dict with success, new version, stage 2 review, or error details.
        """
        content = Content.objects.filter(pk=content_id, owner=user).first()
        if not content:
            return {
                'success': False,
                'error': 'Content not found or unauthorized.',
                'error_type': 'not_found'
            }
        
        current_version = content.current_version
        if not current_version:
            return {
                'success': False,
                'error': 'No current content version available to correct.',
                'error_type': 'no_version'
            }
        
        # 1. Enforce finite automated revision limit (FR-010)
        previous_ai_corrections = content.versions.filter(
            change_summary__icontains='Automated revision'
        ).count()
        
        if previous_ai_corrections >= MAX_AUTOMATED_REVISIONS:
            return {
                'success': False,
                'error': f"Maximum automated correction limit reached ({MAX_AUTOMATED_REVISIONS} revisions). Please edit the draft manually.",
                'error_type': 'limit_reached'
            }
        
        # 2. Get latest review critique
        latest_review = current_version.reviews.order_by('-created_at').first()
        findings = latest_review.findings if latest_review else []
        unsupported = latest_review.unsupported_claims if latest_review else []
        
        # 3. Resolve active AI provider
        adapter, credential, model_name, endpoint = CredentialValidationService.get_active_provider_for_user(
            user=user,
            capability='text'
        )
        if not adapter or not credential:
            return {
                'success': False,
                'error': 'No active AI text provider configured for correction.',
                'error_type': 'no_provider'
            }
        
        # 4. Fetch evidence
        associations = list(
            ResearchContentAssociation.objects.filter(
                content=content
            ).select_related('research')
        )
        
        evidence_lines = []
        for a in associations:
            r = a.research
            evidence_lines.append(f"[{a.citation_index}] {r.title}: {r.summary}")
        evidence_text = "\n".join(evidence_lines)
        
        # 5. Build correction prompt
        findings_str = "\n".join([f"- {f}" for f in findings]) if findings else "- Improve clarity and evidence alignment."
        unsupported_str = "\n".join([f"- {u}" for u in unsupported]) if unsupported else "None flagged."
        
        system_prompt = (
            "You are an expert editorial writer refining a technical content draft. "
            "You must correct and rewrite the draft to address all review findings while maintaining "
            "STRICT grounding in the provided research evidence.\n\n"
            "RULES:\n"
            "1. Fix every issue flagged in the review findings.\n"
            "2. Remove, clarify, or properly substantiate any unsupported claims.\n"
            "3. Keep bracketed citations like [1], [2] aligned with the evidence sources.\n"
            "4. Do NOT invent new facts or external citations."
        )
        
        user_prompt = (
            f"Original Draft:\n{current_version.content_text}\n\n"
            f"Review Findings to Address:\n{findings_str}\n\n"
            f"Unsupported Claims to Fix or Remove:\n{unsupported_str}\n\n"
        )
        if user_notes:
            user_prompt += f"Author Guidance:\n{user_notes}\n\n"
            
        user_prompt += (
            f"Available Evidence Sources:\n{evidence_text}\n\n"
            f"Rewrite the draft addressing the critique above. Output the full corrected draft."
        )
        
        req = GenerationRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model_name=model_name,
            endpoint=endpoint,
            max_tokens=1500,
            temperature=0.4
        )
        
        gen_res = adapter.generate_text(req, credential=credential)
        if not gen_res.success or not gen_res.content:
            return {
                'success': False,
                'error': f"Correction generation failed: {gen_res.error}",
                'error_type': gen_res.error_type or 'generation_failed'
            }
        
        corrected_text = gen_res.content.strip()
        
        # 6. Create immutable next version (immutability + approval safety)
        # Note: new_version.is_approved is False by default, ensuring approval invalidation
        revision_count = previous_ai_corrections + 1
        new_version = ContentVersion.create_next_version(
            content=content,
            created_by=user,
            content_text=corrected_text,
            change_summary=f"Automated revision {revision_count} addressing {len(findings)} review findings"
        )
        
        content.current_version = new_version
        content.save(update_fields=['current_version', 'updated_at'])
        
        # Link research associations to new version
        for a in associations:
            ResearchContentAssociation.objects.create(
                research=a.research,
                content=content,
                content_version=new_version,
                associated_by=user,
                citation_index=a.citation_index,
                relevance_note=f"Carried forward to revision {revision_count}"
            )
        
        # 7. Execute Mandatory AI Quality Review Stage 2 (FR-009, BR-002)
        stage2_review = QualityReviewService.review_version(
            content_version=new_version,
            stage=2,
            user=user,
            provider_adapter=adapter,
            credential=credential,
            model_name=model_name,
            endpoint=endpoint
        )

        from content.services.publishing_service import PublishingPreparationService
        from content.models import WorkflowAuditLog

        PublishingPreparationService.invalidate_preparations_for_content(
            content=content,
            reason=f"Automated revision {revision_count} applied to address review findings.",
            user=user
        )

        WorkflowAuditLog.objects.create(
            content=content,
            content_version=new_version,
            user=user,
            event_type='correction_applied',
            from_state=content.lifecycle_state,
            to_state=content.lifecycle_state,
            message=f"Applied automated revision {revision_count}/{MAX_AUTOMATED_REVISIONS} addressing {len(findings)} review findings.",
            details={'revision_count': revision_count, 'stage2_score': stage2_review.score}
        )
        
        return {
            'success': True,
            'content': content,
            'version': new_version,
            'review': stage2_review,
            'revisions_used': revision_count,
            'revisions_remaining': MAX_AUTOMATED_REVISIONS - revision_count
        }
