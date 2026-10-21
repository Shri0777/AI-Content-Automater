"""
Publishing Preparation & Final Validation Service (Phase 5).

Implements FR-011 (Final Validation), BR-004 (Gate Enforcement), and BR-005 (Mandatory Validation).
Enforces:
- Content lifecycle state must be 'approved'
- ContentVersion must have explicit human approval (is_approved=True)
- ContentVersion must have at least one passing AI Quality Review
- Evidence citation alignment (no hallucinated markers)
- Target platform constraints (Twitter <= 280 chars, LinkedIn <= 3000 chars, Generic <= 5000 chars)
- Formatting platform-specific payloads and invalidation on material edits
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from content.models import Content, ContentReview, ContentVersion, PublishingPreparation, WorkflowAuditLog
from research.models import ResearchContentAssociation

logger = logging.getLogger(__name__)

# Supported platforms and maximum character constraints
PLATFORM_LIMITS = {
    'twitter': 280,
    'linkedin': 3000,
    'generic': 5000,
}


class PublishingPreparationService:
    """
    Validates and prepares approved content versions for publication.
    """

    @staticmethod
    def prepare_content(
        content_id: int,
        user: Any,
        target_platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute final validation and prepare content for publication.
        
        Args:
            content_id: PK of the Content
            user: Authenticated user (ownership verified)
            target_platforms: List of platform keys (defaults to ['twitter', 'linkedin'])
            
        Returns:
            Dict containing success flag, preparation record or actionable error details.
        """
        if not target_platforms:
            target_platforms = ['twitter', 'linkedin']

        # Atomic lock to prevent concurrent preparation races
        with transaction.atomic():
            content = Content.objects.select_for_update().filter(pk=content_id, owner=user).first()
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
                    'error': 'No content version available to prepare.',
                    'error_type': 'no_version'
                }

            # 1. Gate: Verify Explicit Human Approval (BR-006)
            if not current_version.is_approved:
                error_msg = f"Version {current_version.version_number} has not received explicit human approval."
                WorkflowAuditLog.objects.create(
                    content=content,
                    content_version=current_version,
                    user=user,
                    event_type='validation_failed',
                    from_state=content.lifecycle_state,
                    to_state=content.lifecycle_state,
                    message=error_msg,
                    details={'reason': 'unapproved_version', 'version_number': current_version.version_number}
                )
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'approval_required'
                }

            # 2. Gate: Verify Lifecycle State
            if content.lifecycle_state not in ('approved', 'ready_to_publish'):
                error_msg = f"Content must be in 'approved' state to prepare for publishing (currently '{content.lifecycle_state}')."
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'invalid_lifecycle_state'
                }

            # 3. Gate: Verify Quality Review Completion (BR-002, BR-004)
            passing_review = current_version.reviews.filter(status='passed').order_by('-created_at').first()
            if not passing_review:
                error_msg = f"Version {current_version.version_number} must pass AI Quality Review before publishing preparation."
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'review_required'
                }

            # 4. Final Validation: Content checks & platform constraints (FR-011)
            is_valid, validation_results, errors = PublishingPreparationService._validate_content_for_platforms(
                content=content,
                version=current_version,
                target_platforms=target_platforms
            )

            if not is_valid:
                error_summary = "; ".join(errors)
                # Persist failed preparation attempt for observability
                prep = PublishingPreparation.objects.create(
                    content=content,
                    content_version=current_version,
                    prepared_by=user,
                    target_platforms=target_platforms,
                    status='failed',
                    prepared_payload={},
                    validation_results=validation_results,
                    invalidation_reason=error_summary
                )
                WorkflowAuditLog.objects.create(
                    content=content,
                    content_version=current_version,
                    user=user,
                    event_type='validation_failed',
                    from_state=content.lifecycle_state,
                    to_state=content.lifecycle_state,
                    message=f"Publishing preparation validation failed: {error_summary}",
                    details={'validation_results': validation_results, 'errors': errors}
                )
                return {
                    'success': False,
                    'error': f"Final validation failed: {error_summary}",
                    'error_type': 'validation_failed',
                    'validation_results': validation_results,
                    'preparation': prep
                }

            # 5. Idempotency Check: Return existing active preparation if already prepared
            existing_prep = PublishingPreparation.objects.filter(
                content=content,
                content_version=current_version,
                status='prepared',
                target_platforms=target_platforms
            ).first()

            # Build formatted payloads
            prepared_payloads = PublishingPreparationService._format_payloads_for_platforms(
                content=content,
                version=current_version,
                target_platforms=target_platforms
            )

            if existing_prep:
                existing_prep.prepared_payload = prepared_payloads
                existing_prep.validation_results = validation_results
                existing_prep.save(update_fields=['prepared_payload', 'validation_results'])
                prep = existing_prep
            else:
                prep = PublishingPreparation.objects.create(
                    content=content,
                    content_version=current_version,
                    prepared_by=user,
                    target_platforms=target_platforms,
                    status='prepared',
                    prepared_payload=prepared_payloads,
                    validation_results=validation_results
                )

            # Advance lifecycle to 'ready_to_publish' if in 'approved'
            from_state = content.lifecycle_state
            if content.can_transition_to('ready_to_publish'):
                content.transition_to('ready_to_publish')

            WorkflowAuditLog.objects.create(
                content=content,
                content_version=current_version,
                user=user,
                event_type='publishing_prepared',
                from_state=from_state,
                to_state=content.lifecycle_state,
                message=f"Content version v{current_version.version_number} prepared for platforms: {', '.join(target_platforms)}.",
                details={'target_platforms': target_platforms, 'preparation_id': prep.pk}
            )

            return {
                'success': True,
                'content': content,
                'version': current_version,
                'preparation': prep,
                'validation_results': validation_results
            }

    @staticmethod
    def invalidate_preparations_for_content(content: Content, reason: str, user: Optional[Any] = None) -> int:
        """
        Invalidate all active publishing preparations for a content item.
        Called on material edits or approval revocations (BR-007).
        """
        active_preps = PublishingPreparation.objects.filter(
            content=content,
            status='prepared'
        )
        count = active_preps.count()
        if count > 0:
            active_preps.update(
                status='invalidated',
                invalidation_reason=reason
            )
            WorkflowAuditLog.objects.create(
                content=content,
                content_version=content.current_version,
                user=user,
                event_type='approval_invalidated',
                from_state=content.lifecycle_state,
                to_state='in_progress',
                message=f"Invalidated {count} publishing preparations. Reason: {reason}",
                details={'invalidated_count': count, 'reason': reason}
            )
        return count

    @staticmethod
    def _validate_content_for_platforms(
        content: Content,
        version: ContentVersion,
        target_platforms: List[str]
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Evaluate deterministic validation rules for content text against target platforms.
        """
        results = {}
        errors = []
        text = (version.content_text or '').strip()

        # Rule 1: Non-empty content
        if len(text) < 10:
            errors.append("Content text is too short or empty (minimum 10 characters required).")
            results['content_length'] = {'status': 'fail', 'length': len(text)}
        else:
            results['content_length'] = {'status': 'pass', 'length': len(text)}

        # Rule 2: Citation grounding verification
        cited_indices = set(re.findall(r'\[(\d+)\]', text))
        valid_indices = set(
            str(idx) for idx in ResearchContentAssociation.objects.filter(
                content=content
            ).values_list('citation_index', flat=True)
        )
        hallucinated = cited_indices - valid_indices
        if hallucinated:
            errors.append(f"Contains unverified source citations: {sorted(hallucinated)}.")
            results['citations'] = {'status': 'fail', 'hallucinated': sorted(hallucinated)}
        else:
            results['citations'] = {'status': 'pass', 'valid_count': len(cited_indices)}

        # Rule 3: Platform specific constraints
        results['platforms'] = {}
        for platform in target_platforms:
            limit = PLATFORM_LIMITS.get(platform, 5000)
            char_count = len(text)
            if char_count > limit:
                errors.append(
                    f"{platform.capitalize()} character limit exceeded ({char_count}/{limit} characters)."
                )
                results['platforms'][platform] = {
                    'status': 'fail',
                    'char_count': char_count,
                    'limit': limit
                }
            else:
                results['platforms'][platform] = {
                    'status': 'pass',
                    'char_count': char_count,
                    'limit': limit
                }

        is_valid = len(errors) == 0
        return is_valid, results, errors

    @staticmethod
    def _format_payloads_for_platforms(
        content: Content,
        version: ContentVersion,
        target_platforms: List[str]
    ) -> Dict[str, Any]:
        """
        Format clean, platform-specific content payloads with attribution.
        """
        text = (version.content_text or '').strip()
        payloads = {}

        # Fetch evidence sources
        associations = list(
            ResearchContentAssociation.objects.filter(
                content=content
            ).select_related('research')[:3]
        )

        for platform in target_platforms:
            if platform == 'twitter':
                # Compact format
                payloads['twitter'] = {
                    'text': text[:280],
                    'character_count': min(len(text), 280),
                    'truncated': len(text) > 280,
                    'platform': 'twitter'
                }
            elif platform == 'linkedin':
                # Professional layout with evidence footnote
                sources_footnote = "\n\nSources:\n" + "\n".join([
                    f"[{a.citation_index}] {a.research.title} ({a.research.canonical_url or a.research.url})"
                    for a in associations
                ]) if associations else ""
                full_text = text + sources_footnote
                payloads['linkedin'] = {
                    'text': full_text[:3000],
                    'character_count': len(full_text[:3000]),
                    'truncated': len(full_text) > 3000,
                    'platform': 'linkedin'
                }
            else:
                payloads[platform] = {
                    'text': text,
                    'character_count': len(text),
                    'truncated': False,
                    'platform': platform
                }

        return payloads
