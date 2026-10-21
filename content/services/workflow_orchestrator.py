"""
Workflow Orchestrator Service for AI Content Automater V2 (Phase 5).

Provides centralized, concurrency-safe, observable workflow transitions across:
- Research discovery & evidence linking
- AI generation & immutable versioning
- Mandatory AI Quality Reviews (Stages 1 & 2)
- Bounded automated AI correction (FR-010 limit)
- Deterministic final validation & human approval gates
- Publishing preparation and material edit invalidation (BR-007)
- Structured workflow audit logging (FR-021)
"""
import logging
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from content.models import (
    Content,
    ContentReview,
    ContentVersion,
    PublishingPreparation,
    WorkflowAuditLog,
)
from research.models import ContentCreationRequest, ResearchContentAssociation

from .publishing_service import PublishingPreparationService

logger = logging.getLogger(__name__)


class WorkflowOrchestratorService:
    """
    Coordinates end-to-end workflow states, validation gates, and audit trails.
    """

    @staticmethod
    def execute_state_transition(
        content_id: int,
        target_state: str,
        user: Any,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an atomic, concurrency-safe lifecycle state transition.
        
        Args:
            content_id: PK of Content to transition
            target_state: Desired lifecycle state
            user: Authenticated user (ownership verified)
            reason: Optional explanation for audit log
            
        Returns:
            Dict containing success flag, updated content, or error details.
        """
        with transaction.atomic():
            content = Content.objects.select_for_update().filter(pk=content_id, owner=user).first()
            if not content:
                return {
                    'success': False,
                    'error': 'Content not found or unauthorized.',
                    'error_type': 'not_found'
                }

            from_state = content.lifecycle_state

            # Check state machine transition validity
            if not content.can_transition_to(target_state):
                error_msg = f"Illegal transition from '{from_state}' to '{target_state}'."
                WorkflowAuditLog.objects.create(
                    content=content,
                    content_version=content.current_version,
                    user=user,
                    event_type='invalid_transition_attempt',
                    from_state=from_state,
                    to_state=target_state,
                    message=error_msg,
                    details={'reason': reason}
                )
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'invalid_transition'
                }

            # Enforce gate rules for advancing to ready_to_publish or published
            if target_state in ('ready_to_publish', 'published'):
                version = content.current_version
                if not version or not version.is_approved:
                    error_msg = f"Cannot advance to '{target_state}' without an explicitly approved content version."
                    return {
                        'success': False,
                        'error': error_msg,
                        'error_type': 'approval_required'
                    }

            # Apply transition
            content.transition_to(target_state)

            # Invalidate approval/preparation if reverting backwards
            if target_state in ('in_progress', 'draft') and from_state in ('approved', 'ready_to_publish'):
                PublishingPreparationService.invalidate_preparations_for_content(
                    content=content,
                    reason=f"State transitioned backwards to '{target_state}'. {reason or ''}".strip(),
                    user=user
                )

            # Log audit event
            WorkflowAuditLog.objects.create(
                content=content,
                content_version=content.current_version,
                user=user,
                event_type='state_transition',
                from_state=from_state,
                to_state=target_state,
                message=f"Transitioned from {from_state} to {target_state}. {reason or ''}".strip(),
                details={'reason': reason}
            )

            return {
                'success': True,
                'content': content,
                'lifecycle_state': content.lifecycle_state,
                'from_state': from_state,
                'to_state': target_state
            }

    @staticmethod
    def approve_content_version(
        content_id: int,
        user: Any,
        version_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute explicit human approval on a content version.
        Idempotent: Re-approving an already-approved version returns cleanly.
        """
        with transaction.atomic():
            content = Content.objects.select_for_update().filter(pk=content_id, owner=user).first()
            if not content:
                return {
                    'success': False,
                    'error': 'Content not found or unauthorized.',
                    'error_type': 'not_found'
                }

            if version_number:
                version = content.versions.filter(version_number=version_number).first()
            else:
                version = content.current_version

            if not version:
                return {
                    'success': False,
                    'error': 'No content version found to approve.',
                    'error_type': 'no_version'
                }

            # Idempotency check: if already approved, return success
            if version.is_approved and content.lifecycle_state == 'approved':
                return {
                    'success': True,
                    'already_approved': True,
                    'content': content,
                    'version': version,
                    'message': f"Version {version.version_number} is already approved."
                }

            # Explicit human approval
            version.is_approved = True
            version.save(update_fields=['is_approved'])

            from_state = content.lifecycle_state
            if content.can_transition_to('approved'):
                content.transition_to('approved')

            WorkflowAuditLog.objects.create(
                content=content,
                content_version=version,
                user=user,
                event_type='version_approved',
                from_state=from_state,
                to_state=content.lifecycle_state,
                message=f"Version {version.version_number} explicitly approved by {user.email}.",
                details={'version_number': version.version_number}
            )

            return {
                'success': True,
                'already_approved': False,
                'content': content,
                'version': version,
                'message': f"Version {version.version_number} approved successfully."
            }

    @staticmethod
    def handle_material_edit(
        content_id: int,
        user: Any,
        new_content_text: str,
        change_summary: str = ''
    ) -> Dict[str, Any]:
        """
        Create a new version snapshot and invalidate previous approvals and preparations (BR-007).
        """
        with transaction.atomic():
            content = Content.objects.select_for_update().filter(pk=content_id, owner=user).first()
            if not content:
                return {
                    'success': False,
                    'error': 'Content not found or unauthorized.',
                    'error_type': 'not_found'
                }

            from_state = content.lifecycle_state

            # Create immutable new version (is_approved=False by default)
            new_version = ContentVersion.create_next_version(
                content=content,
                created_by=user,
                content_text=new_content_text,
                change_summary=change_summary
            )

            content.current_version = new_version
            if content.lifecycle_state in ('approved', 'ready_to_publish'):
                content.lifecycle_state = 'in_progress'
            content.save(update_fields=['current_version', 'lifecycle_state', 'updated_at'])

            # Invalidate existing publishing preparations
            PublishingPreparationService.invalidate_preparations_for_content(
                content=content,
                reason=f"Material edit: created version v{new_version.version_number}.",
                user=user
            )

            WorkflowAuditLog.objects.create(
                content=content,
                content_version=new_version,
                user=user,
                event_type='material_edit',
                from_state=from_state,
                to_state=content.lifecycle_state,
                message=f"Material edit created version v{new_version.version_number}. Previous approvals invalidated.",
                details={'version_number': new_version.version_number, 'change_summary': change_summary}
            )

            return {
                'success': True,
                'content': content,
                'version': new_version
            }

    @staticmethod
    def prepare_content_for_publishing(
        content_id: int,
        user: Any,
        target_platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute final validation and prepare content for publication.
        """
        return PublishingPreparationService.prepare_content(
            content_id=content_id,
            user=user,
            target_platforms=target_platforms
        )

    @staticmethod
    def get_workflow_summary(content: Content) -> Dict[str, Any]:
        """
        Assemble comprehensive observable workflow metadata for UI dashboards.
        """
        current_version = content.current_version
        reviews = list(current_version.reviews.order_by('stage', '-created_at')) if current_version else []
        latest_review = reviews[0] if reviews else None
        
        # Check review passes
        review_passed = latest_review is not None and latest_review.status == 'passed'

        # Count automated corrections
        ai_revisions_count = content.versions.filter(
            change_summary__icontains='Automated revision'
        ).count()

        # Evidence count
        evidence_count = ResearchContentAssociation.objects.filter(content=content).count()

        # Publishing preparations
        active_prep = content.publishing_preparations.filter(status='prepared').first()
        preparations = list(content.publishing_preparations.all()[:5])

        # Audit history
        recent_audit_logs = list(content.audit_logs.all()[:10])

        # Stage status evaluation for pipeline stepper
        pipeline_stages = [
            {
                'id': 'research',
                'label': '1. Research Discovery',
                'status': 'completed' if evidence_count > 0 else 'pending',
                'details': f"{evidence_count} sources linked" if evidence_count > 0 else "No sources linked"
            },
            {
                'id': 'generation',
                'label': '2. Content Generation',
                'status': 'completed' if current_version else 'pending',
                'details': f"v{current_version.version_number}" if current_version else "Awaiting draft"
            },
            {
                'id': 'review',
                'label': '3. AI Quality Review',
                'status': 'completed' if review_passed else ('needs_revision' if latest_review else 'pending'),
                'details': f"Score: {latest_review.score:.2f} ({latest_review.status})" if latest_review else "Not reviewed"
            },
            {
                'id': 'approval',
                'label': '4. Human Approval',
                'status': 'completed' if (current_version and current_version.is_approved) else 'pending',
                'details': "Approved" if (current_version and current_version.is_approved) else "Approval Pending"
            },
            {
                'id': 'preparation',
                'label': '5. Publishing Prep',
                'status': 'completed' if (active_prep or content.lifecycle_state == 'ready_to_publish') else 'pending',
                'details': "Ready to Publish" if (active_prep or content.lifecycle_state == 'ready_to_publish') else "Unprepared"
            },
        ]

        can_prepare = (
            current_version is not None and
            current_version.is_approved and
            review_passed and
            content.lifecycle_state in ('approved', 'ready_to_publish')
        )

        return {
            'content': content,
            'current_version': current_version,
            'pipeline_stages': pipeline_stages,
            'latest_review': latest_review,
            'review_passed': review_passed,
            'ai_revisions_count': ai_revisions_count,
            'can_auto_correct': ai_revisions_count < 2 and current_version is not None,
            'evidence_count': evidence_count,
            'active_prep': active_prep,
            'preparations': preparations,
            'can_prepare': can_prepare,
            'recent_audit_logs': recent_audit_logs,
        }
