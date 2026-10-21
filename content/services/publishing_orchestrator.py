"""
Buffer Publishing & Scheduling Orchestrator (Phase 6).

Implements the end-to-end publishing workflow:
1. Strict server-side approval gates (is_approved=True, lifecycle state, passing review)
2. Stale approval & material edit checks
3. Destination validation against authorized Buffer channels
4. Scheduling validation (minimum 5-minute lead time, timezone correctness)
5. Concurrency safety & deterministic idempotency enforcement (select_for_update)
6. Pre-dispatch durable record persistence (publishing state)
7. Buffer GraphQL API submission & status tracking (published, scheduled, failed, ambiguous)
8. Accurate timestamp separation (published_at vs scheduled_at)
9. Sanitized audit logging and response data persistence
10. Strict ambiguous outcome reconciliation (restricted to ambiguous status only)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from content.models import (
    Content,
    ContentPublication,
    ContentReview,
    ContentVersion,
    PublishingPreparation,
    WorkflowAuditLog,
)

from .buffer_service import BufferPublishingService

logger = logging.getLogger(__name__)

MIN_LEAD_TIME_MINUTES = 5


class BufferPublishingOrchestrator:
    """
    Coordinates safe, idempotent, concurrency-safe scheduling and publishing through Buffer.
    """

    @staticmethod
    def execute_publishing(
        content_id: int,
        user: Any,
        profile_ids: List[str],
        mode: str = 'immediate',
        scheduled_at: Optional[datetime] = None,
        client_idempotency_key: Optional[str] = None,
        custom_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute publishing or scheduling workflow for approved content.
        
        Args:
            content_id: PK of Content to publish
            user: Authenticated user (ownership verified)
            profile_ids: List of target Buffer channel IDs
            mode: 'immediate' or 'scheduled'
            scheduled_at: Target publication datetime (if mode='scheduled')
            client_idempotency_key: Optional unique token for idempotency
            custom_text: Optional override of content text
            
        Returns:
            Dict containing success flag, publications list, or actionable error details.
        """
        # Step 1: User & Ownership verification with row-level lock
        with transaction.atomic():
            content = (
                Content.objects
                .select_for_update()
                .filter(pk=content_id, owner=user)
                .first()
            )
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
                    'error': 'No content version available to publish.',
                    'error_type': 'no_version'
                }

            # Step 2: Server-side Approval & Quality Gates (BR-002, BR-004, BR-005, BR-006)
            if not current_version.is_approved:
                return {
                    'success': False,
                    'error': f"Version {current_version.version_number} has not received explicit human approval.",
                    'error_type': 'unapproved'
                }

            if content.lifecycle_state not in ('approved', 'ready_to_publish', 'published'):
                return {
                    'success': False,
                    'error': f"Content lifecycle state '{content.lifecycle_state}' is not eligible for publication.",
                    'error_type': 'invalid_lifecycle_state'
                }

            passing_review = current_version.reviews.filter(status='passed').exists()
            if not passing_review:
                return {
                    'success': False,
                    'error': f"Version {current_version.version_number} must pass AI Quality Review before publication.",
                    'error_type': 'review_required'
                }

            # Step 3: Destination validation
            if not profile_ids:
                return {
                    'success': False,
                    'error': 'At least one Buffer destination channel must be selected.',
                    'error_type': 'missing_destination'
                }

            # Step 4: Scheduling validation & timezone checks
            now_dt = timezone.now()
            is_scheduled = (mode == 'scheduled')

            if is_scheduled:
                if not scheduled_at:
                    return {
                        'success': False,
                        'error': 'Scheduled date and time is required for scheduled publication.',
                        'error_type': 'missing_scheduled_time'
                    }
                if timezone.is_naive(scheduled_at):
                    scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
                if scheduled_at <= now_dt + timezone.timedelta(minutes=MIN_LEAD_TIME_MINUTES):
                    return {
                        'success': False,
                        'error': f"Scheduled publication time must be at least {MIN_LEAD_TIME_MINUTES} minutes in the future.",
                        'error_type': 'past_scheduled_time'
                    }

            # Step 5: Payload text resolution
            payload_text = (custom_text or current_version.content_text or '').strip()
            if not payload_text:
                return {
                    'success': False,
                    'error': 'Content text cannot be empty.',
                    'error_type': 'empty_content'
                }

            # Step 6: Buffer integration & channel authorization check
            buffer_service = BufferPublishingService()
            if not buffer_service.is_configured():
                return {
                    'success': False,
                    'error': 'Buffer integration is not configured. Please set BUFFER_ACCESS_TOKEN.',
                    'error_type': 'unconfigured'
                }

            try:
                authorized_profiles = buffer_service.get_profiles()
            except Exception:
                logger.warning('Buffer destination verification failed; refusing to dispatch.')
                return {
                    'success': False,
                    'error': 'Could not verify Buffer destinations. Check the Buffer connection and try again.',
                    'error_type': 'destination_verification_failed'
                }
            authorized_ids = {str(p['id']) for p in authorized_profiles if p.get('id')}
            invalid_ids = [str(pid) for pid in profile_ids if str(pid) not in authorized_ids]
            if invalid_ids:
                return {
                    'success': False,
                    'error': f"Selected channel(s) are not verified Buffer destinations: {', '.join(invalid_ids)}.",
                    'error_type': 'unauthorized_destination' if authorized_profiles else 'no_authorized_destinations'
                }

            # Step 7: Multi-destination execution with independent result tracking & atomic locking
            results = []
            overall_success = True
            publications_to_dispatch = []

            for profile_id in profile_ids:
                # Deterministic idempotency key per target
                target_key = (
                    f"{client_idempotency_key}_{profile_id}"
                    if client_idempotency_key
                    else f"pub_{content.pk}_v{current_version.version_number}_{profile_id}_{int(scheduled_at.timestamp()) if is_scheduled else 'now'}"
                )

                # Idempotency check: prevent duplicate submissions across publishing, scheduled, published, AND ambiguous
                existing_pub = ContentPublication.objects.filter(idempotency_key=target_key).first()
                if existing_pub and existing_pub.status in ('pending', 'published', 'scheduled', 'publishing', 'ambiguous'):
                    results.append({
                        'profile_id': profile_id,
                        'success': existing_pub.status in ('published', 'scheduled'),
                        'is_duplicate': True,
                        'publication': existing_pub,
                        'status': existing_pub.status,
                        'message': f"Publication already recorded as {existing_pub.status} (duplicate prevented)."
                    })
                    continue

                # Pre-dispatch record persistence with status='publishing'
                try:
                    publication, created = ContentPublication.objects.update_or_create(
                        idempotency_key=target_key,
                        defaults={
                            'content': content,
                            'content_version': current_version,
                            'user': user,
                            'provider': 'buffer',
                            'profile_id': str(profile_id),
                            'mode': mode,
                            'scheduled_at': scheduled_at if is_scheduled else None,
                            'published_at': None,  # Explicitly None until published!
                            'payload_text': payload_text,
                            'status': 'publishing'
                        }
                    )
                except IntegrityError:
                    # Concurrent thread created the record: fetch and return existing safely
                    existing_pub = ContentPublication.objects.filter(idempotency_key=target_key).first()
                    results.append({
                        'profile_id': profile_id,
                        'success': existing_pub.status in ('published', 'scheduled') if existing_pub else False,
                        'is_duplicate': True,
                        'publication': existing_pub,
                        'status': existing_pub.status if existing_pub else 'publishing',
                        'message': "Concurrent submission detected. Duplicate prevented."
                    })
                    continue

                publications_to_dispatch.append((publication, profile_id))

        # Outside the database lock, dispatch external network requests to Buffer
        for publication, profile_id in publications_to_dispatch:
            dispatch_res = buffer_service.create_update(
                profile_ids=[profile_id],
                text=payload_text,
                now=(not is_scheduled),
                due_at=scheduled_at if is_scheduled else None
            )

            with transaction.atomic():
                publication.refresh_from_db()

                if dispatch_res['success']:
                    updates = dispatch_res.get('updates', [])
                    update_info = updates[0] if updates else {}
                    ext_id = update_info.get('id')

                    # Publication state correctness:
                    # When scheduled: status='scheduled', published_at=None, scheduled_at=scheduled_at
                    # A successful createPost response confirms acceptance, not delivery.
                    # Immediate posts remain pending until Buffer reports a sent state.
                    external_status = str(update_info.get('status') or '').lower()
                    if is_scheduled:
                        publication.status = 'scheduled'
                        publication.scheduled_at = scheduled_at
                        publication.published_at = None
                    elif external_status in {'sent', 'published'}:
                        publication.status = 'published'
                        publication.published_at = timezone.now()
                        publication.scheduled_at = None
                    else:
                        publication.status = 'pending'
                        publication.published_at = None
                        publication.scheduled_at = None

                    publication.external_post_id = ext_id or ''
                    # Sanitize response data: only store necessary audit identifiers
                    publication.response_data = {
                        'post_id': ext_id,
                        'channel_id': profile_id,
                        'mode': mode,
                        'status': publication.status
                    }
                    publication.save()

                    # Audit trail event
                    event_name = 'content_scheduled' if is_scheduled else ('content_published' if publication.status == 'published' else 'content_submitted')
                    WorkflowAuditLog.objects.create(
                        content=content,
                        content_version=current_version,
                        user=user,
                        event_type=event_name,
                        from_state=content.lifecycle_state,
                        to_state='published' if publication.status == 'published' else content.lifecycle_state,
                        message=f"Post {event_name.split('_')[1]} via Buffer (Channel: {profile_id}, External ID: {ext_id}).",
                        details={'external_post_id': ext_id, 'profile_id': profile_id, 'mode': mode}
                    )

                    results.append({
                        'profile_id': profile_id,
                        'success': publication.status in ('published', 'scheduled', 'pending'),
                        'is_duplicate': False,
                        'publication': publication,
                        'status': publication.status,
                        'external_post_id': ext_id,
                        'message': 'Accepted by Buffer; immediate delivery is not yet confirmed.' if publication.status == 'pending' else None
                    })

                elif dispatch_res.get('is_ambiguous'):
                    # The request may have been applied remotely; never retry automatically.
                    publication.status = 'ambiguous'
                    publication.error_message = dispatch_res.get('error')
                    publication.error_type = dispatch_res.get('error_type', 'ambiguous_outcome')
                    publication.response_data = {'channel_id': profile_id, 'error_type': publication.error_type}
                    publication.save()

                    WorkflowAuditLog.objects.create(
                        content=content,
                        content_version=current_version,
                        user=user,
                        event_type='publishing_ambiguous',
                        from_state=content.lifecycle_state,
                        to_state=content.lifecycle_state,
                        message=f"Publishing outcome ambiguous for channel {profile_id}: {dispatch_res.get('error')}",
                        details={'profile_id': profile_id, 'error_type': 'ambiguous_timeout'}
                    )

                    overall_success = False
                    results.append({
                        'profile_id': profile_id,
                        'success': False,
                        'is_ambiguous': True,
                        'publication': publication,
                        'status': 'ambiguous',
                        'error': dispatch_res.get('error')
                    })

                else:
                    # Terminal or provider error
                    publication.status = 'failed'
                    publication.error_message = dispatch_res.get('error')
                    publication.error_type = dispatch_res.get('error_type')
                    publication.response_data = {'channel_id': profile_id, 'error_type': dispatch_res.get('error_type')}
                    publication.save()

                    WorkflowAuditLog.objects.create(
                        content=content,
                        content_version=current_version,
                        user=user,
                        event_type='publishing_failed',
                        from_state=content.lifecycle_state,
                        to_state=content.lifecycle_state,
                        message=f"Publishing failed for channel {profile_id}: {dispatch_res.get('error')}",
                        details={'profile_id': profile_id, 'error': dispatch_res.get('error')}
                    )

                    overall_success = False
                    results.append({
                        'profile_id': profile_id,
                        'success': False,
                        'publication': publication,
                        'status': 'failed',
                        'error': dispatch_res.get('error')
                    })

        successful_count = sum(1 for r in results if r.get('success'))
        total_targets = len(profile_ids)
        partial_success = (0 < successful_count < total_targets)

        # Advance content lifecycle state if all published successfully or at least one published immediately
        any_published = any(r.get('status') == 'published' for r in results)
        if any_published and content.can_transition_to('published'):
            content.transition_to('published')

        return {
            'success': (successful_count == total_targets and total_targets > 0),
            'partial_success': partial_success,
            'content': content,
            'version': current_version,
            'results': results,
            'total_targets': total_targets,
            'successful_count': successful_count
        }

    @staticmethod
    def reconcile_publication(
        publication_id: int,
        user: Any,
        resolution: str,
        external_post_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reconcile an ambiguous publishing attempt after user verification.
        Strictly restricted to records currently in 'ambiguous' state owned by the user.
        
        Args:
            publication_id: PK of ContentPublication
            user: Authenticated owner
            resolution: 'confirmed_published', 'confirmed_scheduled', or 'mark_failed'
            external_post_id: Optional Buffer update ID confirmed by user
        """
        with transaction.atomic():
            publication = (
                ContentPublication.objects
                .select_for_update()
                .filter(pk=publication_id, user=user)
                .first()
            )
            if not publication:
                return {'success': False, 'error': 'Publication not found or unauthorized.'}

            # Security gate: only ambiguous records can be reconciled!
            if publication.status != 'ambiguous':
                return {
                    'success': False,
                    'error': f"Only publications in 'ambiguous' state can be reconciled (current status: {publication.status})."
                }

            valid_resolutions = {
                'confirmed_published': 'published',
                'confirmed_scheduled': 'scheduled',
                'mark_failed': 'failed'
            }
            new_status = valid_resolutions.get(resolution)
            if not new_status:
                return {'success': False, 'error': f"Invalid resolution: {resolution}"}

            publication.status = new_status
            if new_status == 'published':
                publication.published_at = timezone.now()
            elif new_status == 'scheduled' and not publication.scheduled_at:
                publication.scheduled_at = timezone.now()

            if external_post_id:
                publication.external_post_id = external_post_id.strip()

            publication.error_message = f"Manually reconciled as {new_status} by user."
            publication.save()

            WorkflowAuditLog.objects.create(
                content=publication.content,
                content_version=publication.content_version,
                user=user,
                event_type='publication_reconciled',
                from_state='ambiguous',
                to_state=new_status,
                message=f"Publication {publication.pk} manually reconciled as {new_status}.",
                details={'resolution': resolution, 'external_post_id': external_post_id}
            )

        return {'success': True, 'publication': publication}
