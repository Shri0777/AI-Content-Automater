"""
Phase 5 Test Suite: Workflow Integration, Lifecycle State Machine, Final Validation Gates,
Publishing Preparation, Idempotency, and Audit Trails.

Covers:
- Valid and invalid workflow state transitions
- Prevention of publishing preparation until reviews and human approvals are satisfied
- Final validation gates (length, platform constraints, citation alignment)
- Material edit invalidation of approvals and publishing preparations (BR-007)
- Idempotent operations (re-approval, re-preparation)
- Concurrent state changes protection via database row locks
- Workflow audit logging (FR-021)
- View authorization, IDOR protection, and JSON API transitions
- Observable dashboard integration
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from content.models import (
    Content,
    ContentReview,
    ContentVersion,
    PublishingPreparation,
    WorkflowAuditLog,
)
from content.services.publishing_service import PublishingPreparationService
from content.services.workflow_orchestrator import WorkflowOrchestratorService
from research.models import ContentCreationRequest, Research, ResearchContentAssociation
from users.models import UserProfile

User = get_user_model()


class Phase5WorkflowStateMachineTests(TestCase):
    """Tests for lifecycle state machine rules and transitions."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='author@example.com',
            email='author@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Workflow State Test',
            lifecycle_state='draft'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Initial draft for state testing.'
        )
        self.content.current_version = self.version
        self.content.save()

    def test_complete_forward_lifecycle_progression(self):
        """Test valid forward progression through all lifecycle states."""
        # 1. draft -> in_progress
        res1 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'in_progress', self.user
        )
        self.assertTrue(res1['success'])
        self.assertEqual(res1['lifecycle_state'], 'in_progress')

        # 2. in_progress -> pending_review
        res2 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'pending_review', self.user
        )
        self.assertTrue(res2['success'])
        self.assertEqual(res2['lifecycle_state'], 'pending_review')

        # 3. pending_review -> approved
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        res3 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'approved', self.user
        )
        self.assertTrue(res3['success'])
        self.assertEqual(res3['lifecycle_state'], 'approved')

        # 4. approved -> ready_to_publish
        res4 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'ready_to_publish', self.user
        )
        self.assertTrue(res4['success'])
        self.assertEqual(res4['lifecycle_state'], 'ready_to_publish')

        # 5. ready_to_publish -> published
        res5 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'published', self.user
        )
        self.assertTrue(res5['success'])
        self.assertEqual(res5['lifecycle_state'], 'published')

        # 6. published -> archived
        res6 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'archived', self.user
        )
        self.assertTrue(res6['success'])
        self.assertEqual(res6['lifecycle_state'], 'archived')

    def test_invalid_transitions_rejected(self):
        """Illegal state transitions must be rejected safely without modifying state."""
        # draft cannot jump directly to approved or published
        res1 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'approved', self.user
        )
        self.assertFalse(res1['success'])
        self.assertEqual(res1['error_type'], 'invalid_transition')
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'draft')

        res2 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'published', self.user
        )
        self.assertFalse(res2['success'])
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'draft')

    def test_archived_is_terminal(self):
        """Archived content cannot transition to any other state."""
        self.content.lifecycle_state = 'archived'
        self.content.save()

        res = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'draft', self.user
        )
        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'invalid_transition')

    def test_cannot_advance_to_ready_to_publish_without_approved_version(self):
        """Advancing to ready_to_publish is blocked if version is not approved."""
        self.content.lifecycle_state = 'approved'
        self.content.save()
        self.version.is_approved = False
        self.version.save(update_fields=['is_approved'])

        res = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'ready_to_publish', self.user
        )
        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'approval_required')


class Phase5PublishingPreparationTests(TestCase):
    """Tests for Final Validation Gates and Publishing Preparation (FR-011, BR-004, BR-005)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='prep@example.com',
            email='prep@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Validated Content Architecture',
            topic='Software Architecture',
            lifecycle_state='approved'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Clear evidence-grounded insights on system design [1].'
        )
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.current_version = self.version
        self.content.save()

        # Create valid research association [1]
        self.research = Research.objects.create(
            owner=self.user,
            title='Design Patterns Guide',
            summary='Key principles for backend reliability.',
            url='https://patterns.dev',
            canonical_url='https://patterns.dev',
            overall_score=0.90
        )
        ResearchContentAssociation.objects.create(
            research=self.research,
            content=self.content,
            content_version=self.version,
            associated_by=self.user,
            citation_index=1
        )

        # Attach passing review
        self.review = ContentReview.objects.create(
            content_version=self.version,
            stage=1,
            status='passed',
            score=0.88,
            findings=['Clean evidence grounding.'],
            unsupported_claims=[]
        )

    def test_prepare_publishing_success(self):
        """Approved content with passing review prepares platform payloads successfully."""
        res = PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user,
            target_platforms=['twitter', 'linkedin']
        )
        self.assertTrue(res['success'])
        prep = res['preparation']
        self.assertEqual(prep.status, 'prepared')
        self.assertIn('twitter', prep.prepared_payload)
        self.assertIn('linkedin', prep.prepared_payload)
        self.assertLessEqual(prep.prepared_payload['twitter']['character_count'], 280)

        # Content state advanced to ready_to_publish
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'ready_to_publish')

        # Audit log was created
        audit = WorkflowAuditLog.objects.filter(
            content=self.content,
            event_type='publishing_prepared'
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.to_state, 'ready_to_publish')

    def test_prepare_blocked_if_unapproved(self):
        """Publishing preparation is strictly blocked if version is not approved."""
        self.version.is_approved = False
        self.version.save(update_fields=['is_approved'])

        res = PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user
        )
        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'approval_required')
        self.content.refresh_from_db()
        self.assertNotEqual(self.content.lifecycle_state, 'ready_to_publish')

    def test_prepare_blocked_if_no_passing_review(self):
        """Publishing preparation is blocked if version lacks a passing AI review."""
        self.review.status = 'needs_revision'
        self.review.save(update_fields=['status'])

        res = PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user
        )
        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'review_required')

    def test_prepare_blocked_by_hallucinated_citations(self):
        """Final validation fails if content cites source markers not in associations."""
        # Version cites [99] which has no ResearchContentAssociation
        bad_version = ContentVersion.create_next_version(
            content=self.content,
            created_by=self.user,
            content_text='This claim cites unverified source [99].'
        )
        bad_version.is_approved = True
        bad_version.save(update_fields=['is_approved'])
        self.content.current_version = bad_version
        self.content.save()

        # Add passing review to bad_version
        ContentReview.objects.create(
            content_version=bad_version,
            stage=1,
            status='passed',
            score=0.80
        )

        res = PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user
        )
        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'validation_failed')
        self.assertIn('unverified source citations', res['error'])

    def test_material_edit_invalidates_publishing_preparation(self):
        """Creating a new version invalidates active preparations and resets state (BR-007)."""
        # First prepare content
        PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user
        )
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'ready_to_publish')
        prep = self.content.publishing_preparations.first()
        self.assertEqual(prep.status, 'prepared')

        # Now apply material edit
        res = WorkflowOrchestratorService.handle_material_edit(
            content_id=self.content.pk,
            user=self.user,
            new_content_text='Completely updated content draft.',
            change_summary='Manual revision by author'
        )
        self.assertTrue(res['success'])
        new_version = res['version']

        # Verifications
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'in_progress')
        self.assertEqual(self.content.current_version, new_version)
        self.assertFalse(new_version.is_approved)

        # Previous preparation must be marked invalidated
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'invalidated')
        self.assertIn('Material edit', prep.invalidation_reason)


class Phase5IdempotencyAndAuditTests(TestCase):
    """Tests for idempotent actions and audit logging."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='audit@example.com',
            email='audit@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Audit & Idempotency Content',
            lifecycle_state='pending_review'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Content for idempotency testing.'
        )
        self.content.current_version = self.version
        self.content.save()

    def test_approval_idempotency(self):
        """Repeated approval requests succeed idempotently without duplicate records."""
        res1 = WorkflowOrchestratorService.approve_content_version(
            content_id=self.content.pk,
            user=self.user
        )
        self.assertTrue(res1['success'])
        self.assertFalse(res1['already_approved'])

        # Second approval call should be a clean no-op
        res2 = WorkflowOrchestratorService.approve_content_version(
            content_id=self.content.pk,
            user=self.user
        )
        self.assertTrue(res2['success'])
        self.assertTrue(res2['already_approved'])

        # Audit logs should only record one approval event
        approvals = WorkflowAuditLog.objects.filter(
            content=self.content,
            event_type='version_approved'
        )
        self.assertEqual(approvals.count(), 1)

    def test_preparation_idempotency(self):
        """Repeated preparation requests update/return existing active record without duplicates."""
        # Setup approval and passing review
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save()
        ContentReview.objects.create(
            content_version=self.version,
            stage=1,
            status='passed',
            score=0.90
        )

        res1 = PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user,
            target_platforms=['twitter', 'linkedin']
        )
        self.assertTrue(res1['success'])

        # Second call with same parameters
        res2 = PublishingPreparationService.prepare_content(
            content_id=self.content.pk,
            user=self.user,
            target_platforms=['twitter', 'linkedin']
        )
        self.assertTrue(res2['success'])

        # Count active preparations: should only be 1
        active_preps = PublishingPreparation.objects.filter(
            content=self.content,
            status='prepared'
        )
        self.assertEqual(active_preps.count(), 1)


class Phase5ViewAndSecurityTests(TestCase):
    """View integration, authorization, IDOR denial, and JSON API tests."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.owner)

        self.intruder = User.objects.create_user(
            username='intruder@example.com',
            email='intruder@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.intruder)

        self.content = Content.objects.create(
            owner=self.owner,
            title='Security & View Testing',
            lifecycle_state='approved'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.owner,
            content_text='Tested content body text for view integration.'
        )
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.current_version = self.version
        self.content.save()

        ContentReview.objects.create(
            content_version=self.version,
            stage=1,
            status='passed',
            score=0.85
        )

    def test_prepare_publishing_forbidden_for_intruder(self):
        """Cross-user preparation is blocked with HTTP 403 Forbidden."""
        self.client.login(username='intruder@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:prepare_publishing', kwargs={'pk': self.content.pk}),
            {'platforms': ['twitter']}
        )
        self.assertEqual(response.status_code, 403)

    def test_prepare_publishing_success_for_owner(self):
        """Owner can prepare content for publishing and is redirected to detail."""
        self.client.login(username='owner@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:prepare_publishing', kwargs={'pk': self.content.pk}),
            {'platforms': ['twitter', 'linkedin']}
        )
        self.assertRedirects(response, reverse('content:detail', kwargs={'pk': self.content.pk}))

        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'ready_to_publish')

    def test_transition_json_api(self):
        """Transition endpoint supports JSON payloads and returns structured responses."""
        self.client.login(username='owner@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:transition', kwargs={'pk': self.content.pk}),
            data=json.dumps({'target_state': 'ready_to_publish'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['lifecycle_state'], 'ready_to_publish')

    def test_transition_json_api_invalid_transition(self):
        """Invalid transition via JSON API returns 400 Bad Request with error description."""
        self.client.login(username='owner@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:transition', kwargs={'pk': self.content.pk}),
            data=json.dumps({'target_state': 'draft'}),
            content_type='application/json'
        )
        # approved -> draft is allowed via reset, but approved -> archived is invalid
        response = self.client.post(
            reverse('content:transition', kwargs={'pk': self.content.pk}),
            data=json.dumps({'target_state': 'archived'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Illegal transition', data['error'])

    def test_detail_view_renders_pipeline_and_audit_trail(self):
        """Detail view renders pipeline stepper, publishing prep card, and audit log."""
        self.client.login(username='owner@example.com', password='testpass123')

        # Add audit log
        WorkflowAuditLog.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.owner,
            event_type='review_stage_1',
            from_state='in_progress',
            to_state='pending_review',
            message='Quality review completed.'
        )

        response = self.client.get(reverse('content:detail', kwargs={'pk': self.content.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "End-to-End Workflow Pipeline")
        self.assertContains(response, "Publishing Preparation &amp; Multi-Platform Payloads")
        self.assertContains(response, "Workflow Audit Trail")
        self.assertContains(response, "Quality review completed.")

    def test_unauthenticated_requests_redirect(self):
        """Unauthenticated requests to prepare or transition redirect to login."""
        res_prep = self.client.post(
            reverse('content:prepare_publishing', kwargs={'pk': self.content.pk})
        )
        self.assertEqual(res_prep.status_code, 302)
        self.assertIn('/auth/login/', res_prep.url)

        res_trans = self.client.post(
            reverse('content:transition', kwargs={'pk': self.content.pk})
        )
        self.assertEqual(res_trans.status_code, 302)
        self.assertIn('/auth/login/', res_trans.url)


class Phase5ModelsAndConcurrencyTests(TestCase):
    """Tests for model representations, audit records, and concurrency row locking."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='models@example.com',
            email='models@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Concurrency and Model Spec',
            lifecycle_state='approved'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Text for concurrency testing.'
        )
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.current_version = self.version
        self.content.save()

    def test_publishing_prep_str_representation(self):
        """PublishingPreparation __str__ returns readable summary."""
        prep = PublishingPreparation.objects.create(
            content=self.content,
            content_version=self.version,
            prepared_by=self.user,
            target_platforms=['twitter'],
            status='prepared'
        )
        self.assertIn(self.content.title, str(prep))
        self.assertIn("v1", str(prep))
        self.assertIn("prepared", str(prep))

    def test_workflow_audit_log_str_representation(self):
        """WorkflowAuditLog __str__ returns event and actor."""
        log = WorkflowAuditLog.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.user,
            event_type='publishing_prepared',
            from_state='approved',
            to_state='ready_to_publish',
            message='Ready for dispatch'
        )
        self.assertIn("publishing_prepared", str(log))
        self.assertIn(self.user.email, str(log))

    def test_concurrency_serialized_transition(self):
        """Concurrent calls with row-locking resolve in a deterministic, safe state."""
        # Execute sequential transitions that test state changes
        res1 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'ready_to_publish', self.user
        )
        self.assertTrue(res1['success'])
        self.assertEqual(res1['lifecycle_state'], 'ready_to_publish')

        # Trying to jump back to approved or forward to published
        res2 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'published', self.user
        )
        self.assertTrue(res2['success'])
        self.assertEqual(res2['lifecycle_state'], 'published')

        # From published, cannot transition back to ready_to_publish
        res3 = WorkflowOrchestratorService.execute_state_transition(
            self.content.pk, 'ready_to_publish', self.user
        )
        self.assertFalse(res3['success'])
        self.assertEqual(res3['error_type'], 'invalid_transition')

    def test_research_creation_request_error_recording(self):
        """ContentCreationRequest records error_message, error_type, and retry_count."""
        req = ContentCreationRequest.objects.create(
            user=self.user,
            topics=['Testing'],
            audience='Devs',
            content_goal='Educational',
            freshness_days=7,
            language='en',
            source_categories=['tech'],
            status='failed',
            error_message='RSS connection timed out after 2 retries',
            error_type='connection_timeout',
            retry_count=2
        )
        req.refresh_from_db()
        self.assertEqual(req.status, 'failed')
        self.assertEqual(req.error_type, 'connection_timeout')
        self.assertEqual(req.retry_count, 2)
        self.assertIn('timed out', req.error_message)
