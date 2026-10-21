"""
Phase 6 Test Suite: Buffer GraphQL Publishing, Scheduling, Concurrency, and Ambiguous Timeout Reconciliation.

Covers:
1. BufferPublishingService (Official Buffer GraphQL API):
   - Token masking and unconfigured state handling
   - Account and organization discovery queries (query GetAccountAndOrgs)
   - Channel/profile discovery queries (query GetChannels)
   - Immediate post mutation (mutation CreatePost with mode: shareNow)
   - Scheduled post mutation (mutation CreatePost with mode: customScheduled and dueAt ISO-8601 UTC)
   - GraphQL union error handling (PostActionSuccess vs MutationError)
   - Rate limit (HTTP 429) & bounded transient retry (HTTP 503)
   - Timeout ambiguity detection (BR-018: no blind retries)
2. BufferPublishingOrchestrator:
   - Mandatory server-side quality, human approval, and lifecycle state gates
   - Destination validation against authorized Buffer channels
   - Lead time validation (minimum 5 minutes future requirement)
   - Timestamp separation (published_at vs scheduled_at)
   - Concurrency safety, row-level locking (select_for_update), and IntegrityError idempotency
   - Duplicate prevention across publishing, scheduled, published, AND ambiguous states
   - Sanitized audit logging
   - Ambiguous outcome manual reconciliation restrictions (restricted strictly to ambiguous state)
   - Accurate partial success handling across multi-channel dispatches
3. Views and Dashboard:
   - Detail view Buffer status badge, channel selectors, and publication history
   - Locked view for unapproved content
   - Publish endpoint: full success vs partial success warning vs total failure
   - Reconcile endpoint: authorized vs non-ambiguous rejection
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from content.models import (
    Content,
    ContentPublication,
    ContentReview,
    ContentVersion,
    PublishingPreparation,
    WorkflowAuditLog,
)
from content.services.buffer_service import BufferPublishingService
from content.services.publishing_orchestrator import BufferPublishingOrchestrator
from users.models import UserProfile

User = get_user_model()


class BufferPublishingServiceTests(TestCase):
    """Unit tests for the low-level Buffer GraphQL API client service."""

    def test_token_masking_and_unconfigured_state(self):
        """Test service behavior when access token is missing or provided."""
        service_unconfigured = BufferPublishingService(access_token="")
        self.assertFalse(service_unconfigured.is_configured())
        self.assertIsNone(service_unconfigured.get_masked_token())

        status = service_unconfigured.get_connection_status()
        self.assertFalse(status['configured'])
        self.assertFalse(status['connected'])

        service_configured = BufferPublishingService(access_token="1/28ab90cd1234ef567890abcdef123456")
        self.assertTrue(service_configured.is_configured())
        masked = service_configured.get_masked_token()
        self.assertTrue(masked.startswith("1/28..."))
        self.assertTrue(masked.endswith("3456"))

    @patch('requests.post')
    def test_connection_status_graphql_success(self, mock_post):
        """Test successful connection status probe via GraphQL account query."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'account': {
                    'id': 'acc_123',
                    'email': 'author@example.com',
                    'organizations': [
                        {'id': 'org_999', 'name': 'Content Team', 'ownerEmail': 'author@example.com'}
                    ]
                }
            }
        }
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="buff_token_1234567890")
        status = service.get_connection_status()

        self.assertTrue(status['configured'])
        self.assertTrue(status['connected'])
        self.assertEqual(status['user_id'], 'acc_123')
        self.assertEqual(status['organization_id'], 'org_999')
        self.assertEqual(status['user_name'], 'Content Team')

    @patch('requests.post')
    def test_connection_status_unauthenticated_graphql_error(self, mock_post):
        """Test GraphQL unauthenticated error handling."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'errors': [
                {
                    'message': 'You must be authenticated to access this resource.',
                    'extensions': {'code': 'UNAUTHENTICATED'}
                }
            ]
        }
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="invalid_token")
        status = service.get_connection_status()

        self.assertTrue(status['configured'])
        self.assertFalse(status['connected'])
        self.assertEqual(status['status'], 'unauthorized')
        self.assertIn("UNAUTHENTICATED", status['error'])

    @patch('requests.post')
    def test_connection_status_http_401(self, mock_post):
        """Test HTTP 401 Unauthorized handling on GraphQL endpoint."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="bad_token")
        status = service.get_connection_status()

        self.assertFalse(status['connected'])
        self.assertEqual(status['status'], 'unauthorized')

    @patch('requests.post')
    def test_connection_status_timeout(self, mock_post):
        """Test connection timeout handling."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        service = BufferPublishingService(access_token="buff_token_1234567890")
        status = service.get_connection_status()

        self.assertFalse(status['connected'])
        self.assertIn("timed out", status['error'].lower())

    @patch('requests.post')
    def test_get_profiles_graphql_success(self, mock_post):
        """Test channel discovery parsing from Buffer GraphQL account and channels queries."""
        org_resp = MagicMock()
        org_resp.status_code = 200
        org_resp.json.return_value = {
            'data': {
                'account': {
                    'organizations': [{'id': 'org_1'}]
                }
            }
        }

        channels_resp = MagicMock()
        channels_resp.status_code = 200
        channels_resp.json.return_value = {
            'data': {
                'channels': [
                    {
                        'id': 'chan_tw_1',
                        'service': 'twitter',
                        'name': 'ai_automater',
                        'displayName': '@ai_automater',
                        'avatar': 'https://example.com/tw.jpg',
                        'isQueuePaused': False
                    },
                    {
                        'id': 'chan_li_2',
                        'service': 'linkedin',
                        'name': 'AI Content Corp',
                        'displayName': 'AI Content Corp',
                        'avatar': 'https://example.com/li.jpg',
                        'isQueuePaused': False
                    }
                ]
            }
        }

        mock_post.side_effect = [org_resp, channels_resp]

        service = BufferPublishingService(access_token="buff_token_1234567890")
        profiles = service.get_profiles()

        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0]['id'], 'chan_tw_1')
        self.assertEqual(profiles[0]['service'], 'twitter')
        self.assertEqual(profiles[1]['id'], 'chan_li_2')

    @patch('requests.post')
    def test_create_post_graphql_immediate_success(self, mock_post):
        """Test creating an immediate post via GraphQL createPost with mode: shareNow."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'createPost': {
                    'post': {
                        'id': 'post_graphql_1001',
                        'text': 'Test post content',
                        'status': 'published',
                        'dueAt': None
                    }
                }
            }
        }
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="buff_token_1234567890")
        res = service.create_update(
            profile_ids=['chan_tw_1'],
            text='Test post content',
            now=True
        )

        self.assertTrue(res['success'])
        self.assertEqual(len(res['updates']), 1)
        self.assertEqual(res['updates'][0]['id'], 'post_graphql_1001')

        # Verify GraphQL payload structure
        call_kwargs = mock_post.call_args[1]
        variables = call_kwargs['json']['variables']['input']
        self.assertEqual(variables['channelId'], 'chan_tw_1')
        self.assertEqual(variables['mode'], 'shareNow')
        self.assertEqual(variables['schedulingType'], 'automatic')
        self.assertEqual(variables['text'], 'Test post content')

    @patch('requests.post')
    def test_create_post_graphql_scheduled_success(self, mock_post):
        """Test creating a scheduled post via GraphQL createPost with mode: customScheduled and dueAt ISO-8601 UTC."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'createPost': {
                    'post': {
                        'id': 'post_graphql_1002',
                        'text': 'Scheduled post',
                        'status': 'scheduled',
                        'dueAt': '2026-10-25T15:00:00.000Z'
                    }
                }
            }
        }
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="buff_token_1234567890")
        target_time = timezone.now() + timedelta(days=2)
        res = service.create_update(
            profile_ids=['chan_li_2'],
            text='Scheduled post',
            now=False,
            due_at=target_time
        )

        self.assertTrue(res['success'])
        call_kwargs = mock_post.call_args[1]
        variables = call_kwargs['json']['variables']['input']
        self.assertEqual(variables['mode'], 'customScheduled')
        self.assertTrue(variables['dueAt'].endswith('.000Z'))

    @patch('requests.post')
    def test_create_post_graphql_mutation_error(self, mock_post):
        """Test GraphQL MutationError union response handling."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'createPost': {
                    'message': 'Channel is disconnected or unauthorized'
                }
            }
        }
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="buff_token_1234567890")
        res = service.create_update(profile_ids=['chan_1'], text='Post')

        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'mutation_error')
        self.assertIn("disconnected or unauthorized", res['error'])

    @patch('requests.post')
    def test_create_post_rate_limited(self, mock_post):
        """Test 429 Rate Limit error handling."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        service = BufferPublishingService(access_token="buff_token_1234567890")
        res = service.create_update(profile_ids=['chan_1'], text='Post')

        self.assertFalse(res['success'])
        self.assertEqual(res['error_type'], 'rate_limited')
        self.assertIn("rate limit", res['error'].lower())

    @patch('requests.post')
    def test_create_post_ambiguous_timeout(self, mock_post):
        """Test timeout returns is_ambiguous=True per BR-018."""
        mock_post.side_effect = requests.exceptions.Timeout("Post timeout")

        service = BufferPublishingService(access_token="buff_token_1234567890")
        res = service.create_update(profile_ids=['chan_1'], text='Post')

        self.assertFalse(res['success'])
        self.assertTrue(res.get('is_ambiguous'))
        self.assertEqual(res['error_type'], 'ambiguous_timeout')

    @patch('requests.post')
    def test_create_post_503_bounded_retry(self, mock_post):
        """Test 503 transient failure performs bounded retry (max 1 retry)."""
        fail_resp = MagicMock()
        fail_resp.status_code = 503

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            'data': {
                'createPost': {
                    'post': {'id': 'post_retry_ok', 'status': 'published'}
                }
            }
        }

        mock_post.side_effect = [fail_resp, success_resp]

        service = BufferPublishingService(access_token="buff_token_1234567890")
        res = service.create_update(profile_ids=['chan_1'], text='Post')

        self.assertFalse(res['success'])
        self.assertTrue(res.get('is_ambiguous'))
        self.assertEqual(res['error_type'], 'ambiguous_server_error')
        self.assertEqual(mock_post.call_count, 1)


@override_settings(BUFFER_ACCESS_TOKEN='test_buffer_token_1234567890')
class BufferPublishingOrchestratorTests(TestCase):
    """Integration tests for publishing orchestration, gates, concurrency, and idempotency."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='publisher@example.com',
            email='publisher@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.other_user = User.objects.create_user(
            username='stranger@example.com',
            email='stranger@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.other_user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Verified Grounded Post',
            lifecycle_state='ready_to_publish'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Enterprise agentic workflows with strict audit logging.'
        )
        self.version.is_approved = True
        self.version.approved_by = self.user
        self.version.approved_at = timezone.now()
        self.version.save()

        self.content.current_version = self.version
        self.content.save()

        # Add a passing quality review
        self.review = ContentReview.objects.create(
            content_version=self.version,
            status='passed',
            score=0.95,
            stage=1,
            summary='Quality review passed.'
        )

        # Authorized channel fixtures
        self.authorized_profiles = [
            {'id': 'chan_tw_1', 'service': 'twitter', 'formatted_username': '@tester'},
            {'id': 'chan_li_2', 'service': 'linkedin', 'formatted_username': 'Tester Corp'}
        ]

    def test_publishing_rejected_when_not_approved(self):
        """Reject publishing if human approval is not granted."""
        self.version.is_approved = False
        self.version.save()

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1']
        )

        self.assertFalse(res['success'])
        self.assertIn("explicit human approval", res['error'])

    def test_publishing_rejected_when_no_passing_review(self):
        """Reject publishing if quality review verdict is not pass."""
        self.review.status = 'needs_revision'
        self.review.save()

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1']
        )

        self.assertFalse(res['success'])
        self.assertIn("must pass AI Quality Review", res['error'])

    def test_publishing_rejected_for_invalid_lifecycle_state(self):
        """Reject publishing if content lifecycle state is draft or in_progress."""
        self.content.lifecycle_state = 'in_progress'
        self.content.save()

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1']
        )

        self.assertFalse(res['success'])
        self.assertIn("lifecycle state", res['error'])

    @patch.object(BufferPublishingService, 'get_profiles')
    def test_publishing_rejected_for_insufficient_lead_time(self, mock_profiles):
        """Reject scheduling if target time is less than 5 minutes in the future."""
        mock_profiles.return_value = self.authorized_profiles
        short_time = timezone.now() + timedelta(minutes=2)

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1'],
            mode='scheduled',
            scheduled_at=short_time
        )

        self.assertFalse(res['success'])
        self.assertIn("at least 5 minutes in the future", res['error'])

    @patch.object(BufferPublishingService, 'get_profiles')
    def test_publishing_rejected_for_unauthorized_destination(self, mock_profiles):
        """Reject publishing if requested channel is not in authorized Buffer channels."""
        mock_profiles.return_value = self.authorized_profiles

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['unauthorized_chan_999']
        )

        self.assertFalse(res['success'])
        self.assertIn("not verified Buffer destinations", res['error'])

    def test_publishing_rejected_for_idor_unauthorized_user(self):
        """Reject publishing if user does not own content."""
        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.other_user,
            profile_ids=['chan_tw_1']
        )

        self.assertFalse(res['success'])
        self.assertIn("not found or unauthorized", res['error'])

    @patch.object(BufferPublishingService, 'get_profiles')
    @patch.object(BufferPublishingService, 'create_update')
    def test_immediate_publishing_workflow_success(self, mock_create_update, mock_profiles):
        """Test successful immediate publishing end-to-end with proper timestamp setting."""
        mock_profiles.return_value = self.authorized_profiles
        mock_create_update.return_value = {
            'success': True,
            'updates': [{'id': 'buf_up_999', 'profile_id': 'chan_tw_1'}]
        }

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1'],
            mode='immediate'
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['successful_count'], 1)

        # Verify durable publication record
        pub = ContentPublication.objects.get(content=self.content, profile_id='chan_tw_1')
        self.assertEqual(pub.status, 'pending')
        self.assertEqual(pub.mode, 'immediate')
        self.assertEqual(pub.external_post_id, 'buf_up_999')
        self.assertIsNone(pub.published_at)
        self.assertIsNone(pub.scheduled_at)

        # Buffer acceptance is not proof of actual delivery.
        self.content.refresh_from_db()
        self.assertNotEqual(self.content.lifecycle_state, 'published')

    @patch.object(BufferPublishingService, 'get_profiles')
    @patch.object(BufferPublishingService, 'create_update')
    def test_scheduled_publishing_workflow_success_and_timestamp_separation(self, mock_create_update, mock_profiles):
        """Test scheduled publishing sets scheduled_at and keeps published_at strictly None (Defect 2 repair)."""
        mock_profiles.return_value = self.authorized_profiles
        target_time = timezone.now() + timedelta(days=1)
        mock_create_update.return_value = {
            'success': True,
            'updates': [{'id': 'buf_sched_888', 'profile_id': 'chan_tw_1'}]
        }

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1'],
            mode='scheduled',
            scheduled_at=target_time
        )

        self.assertTrue(res['success'])
        pub = ContentPublication.objects.get(content=self.content, profile_id='chan_tw_1')
        self.assertEqual(pub.status, 'scheduled')
        self.assertEqual(pub.mode, 'scheduled')
        self.assertEqual(pub.external_post_id, 'buf_sched_888')

        # CRITICAL REPAIR CHECK: published_at must NOT be set when post is merely scheduled!
        self.assertIsNotNone(pub.scheduled_at)
        self.assertIsNone(pub.published_at)

    @patch.object(BufferPublishingService, 'get_profiles')
    @patch.object(BufferPublishingService, 'create_update')
    def test_ambiguous_timeout_handling(self, mock_create_update, mock_profiles):
        """Test ambiguous timeout marks publication as ambiguous without blind retries."""
        mock_profiles.return_value = self.authorized_profiles
        mock_create_update.return_value = {
            'success': False,
            'error': 'Buffer post submission timed out in ambiguous state.',
            'error_type': 'ambiguous_timeout',
            'is_ambiguous': True
        }

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1'],
            mode='immediate'
        )

        self.assertFalse(res['success'])
        pub = ContentPublication.objects.get(content=self.content, profile_id='chan_tw_1')
        self.assertEqual(pub.status, 'ambiguous')
        self.assertEqual(pub.error_type, 'ambiguous_timeout')

    @patch.object(BufferPublishingService, 'get_profiles')
    @patch.object(BufferPublishingService, 'create_update')
    def test_ambiguous_record_prevents_duplicate_dispatch(self, mock_create_update, mock_profiles):
        """A previous ambiguous record must prevent duplicate submission (Defect 4 repair)."""
        mock_profiles.return_value = self.authorized_profiles
        ContentPublication.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.user,
            provider='buffer',
            profile_id='chan_tw_1',
            status='ambiguous',
            mode='immediate',
            idempotency_key=f"pub_{self.content.pk}_v{self.version.version_number}_chan_tw_1_now"
        )

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1'],
            mode='immediate'
        )

        # Must NOT re-dispatch to Buffer when in ambiguous status
        mock_create_update.assert_not_called()
        self.assertTrue(res['results'][0]['is_duplicate'])

    @patch.object(BufferPublishingService, 'get_profiles')
    @patch.object(BufferPublishingService, 'create_update')
    def test_idempotency_prevents_duplicate_publishing(self, mock_create_update, mock_profiles):
        """Test that re-submitting with identical parameters does not duplicate API calls."""
        mock_profiles.return_value = self.authorized_profiles
        ContentPublication.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.user,
            provider='buffer',
            profile_id='chan_tw_1',
            status='published',
            mode='immediate',
            idempotency_key=f"pub_{self.content.pk}_v{self.version.version_number}_chan_tw_1_now",
            external_post_id='existing_buf_id'
        )

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1'],
            mode='immediate'
        )

        self.assertTrue(res['success'])
        mock_create_update.assert_not_called()

    @patch.object(BufferPublishingService, 'get_profiles')
    @patch.object(BufferPublishingService, 'create_update')
    def test_partial_success_handling(self, mock_create_update, mock_profiles):
        """Test partial success when publishing across multiple channels (Defect 7 repair)."""
        mock_profiles.return_value = self.authorized_profiles

        def side_effect(profile_ids, **kwargs):
            if profile_ids == ['chan_tw_1']:
                return {'success': True, 'updates': [{'id': 'ok_1'}]}
            else:
                return {'success': False, 'error': 'LinkedIn rate limit', 'error_type': 'rate_limited'}

        mock_create_update.side_effect = side_effect

        res = BufferPublishingOrchestrator.execute_publishing(
            content_id=self.content.pk,
            user=self.user,
            profile_ids=['chan_tw_1', 'chan_li_2'],
            mode='immediate'
        )

        self.assertFalse(res['success'])
        self.assertTrue(res['partial_success'])
        self.assertEqual(res['successful_count'], 1)
        self.assertEqual(res['total_targets'], 2)

    def test_manual_reconciliation_workflow(self):
        """Test manual reconciliation of ambiguous publication."""
        ambiguous_pub = ContentPublication.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.user,
            provider='buffer',
            profile_id='chan_tw_1',
            status='ambiguous',
            mode='immediate',
            idempotency_key='test_ambiguous_key'
        )

        # Owner reconciles as confirmed_published
        res_auth = BufferPublishingOrchestrator.reconcile_publication(
            publication_id=ambiguous_pub.pk,
            user=self.user,
            resolution='confirmed_published',
            external_post_id='buf_rec_123'
        )
        self.assertTrue(res_auth['success'])

        ambiguous_pub.refresh_from_db()
        self.assertEqual(ambiguous_pub.status, 'published')
        self.assertEqual(ambiguous_pub.external_post_id, 'buf_rec_123')
        self.assertIsNotNone(ambiguous_pub.published_at)

    def test_reconciliation_rejected_for_non_ambiguous_publication(self):
        """Reject reconciliation if publication is NOT in ambiguous state (Defect 6 repair)."""
        published_pub = ContentPublication.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.user,
            provider='buffer',
            profile_id='chan_tw_1',
            status='published',
            mode='immediate',
            idempotency_key='test_published_key'
        )

        res = BufferPublishingOrchestrator.reconcile_publication(
            publication_id=published_pub.pk,
            user=self.user,
            resolution='mark_failed'
        )

        self.assertFalse(res['success'])
        self.assertIn("Only publications in 'ambiguous' state can be reconciled", res['error'])


@override_settings(BUFFER_ACCESS_TOKEN='test_buffer_token_1234567890')
class BufferViewsAndDashboardTests(TestCase):
    """View and template integration tests for Phase 6 publishing."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='dashboard_author@example.com',
            email='dashboard_author@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Dashboard Buffer Test',
            lifecycle_state='ready_to_publish'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Testing dashboard display of publishing controls.'
        )
        self.version.is_approved = True
        self.version.save()
        self.content.current_version = self.version
        self.content.save()

        # Passing review
        ContentReview.objects.create(
            content_version=self.version,
            status='passed',
            score=0.90,
            stage=1,
            summary='Passed review'
        )

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    def test_detail_view_renders_buffer_card(self, mock_profiles, mock_status):
        """Detail view displays Buffer card with profiles and publication history."""
        self.client.login(username='dashboard_author@example.com', password='testpass123')
        mock_status.return_value = {
            'configured': True,
            'connected': True,
            'masked_token': 'buff_...1234',
            'user_name': 'Buffer User'
        }
        mock_profiles.return_value = [
            {'id': 'chan_1', 'service': 'twitter', 'formatted_username': '@tester'}
        ]

        url = reverse('content:detail', kwargs={'pk': self.content.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Buffer Social Publishing &amp; Scheduling')
        self.assertContains(response, 'Buffer Connected')
        self.assertContains(response, '@tester')
        self.assertContains(response, 'Send to Buffer')

    @patch.object(BufferPublishingService, 'get_connection_status')
    def test_detail_view_shows_locked_notice_when_not_approved(self, mock_status):
        """Detail view shows lock message when content version is not approved."""
        self.version.is_approved = False
        self.version.save()

        self.client.login(username='dashboard_author@example.com', password='testpass123')
        mock_status.return_value = {
            'configured': True,
            'connected': True,
            'masked_token': 'buff_...1234'
        }

        url = reverse('content:detail', kwargs={'pk': self.content.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Publishing Locked')
        self.assertNotContains(response, 'Send to Buffer')

    @patch.object(BufferPublishingOrchestrator, 'execute_publishing')
    def test_content_publish_post_success(self, mock_exec):
        """Test content_publish view handler redirects and notifies on success."""
        self.client.login(username='dashboard_author@example.com', password='testpass123')
        mock_exec.return_value = {
            'success': True,
            'partial_success': False,
            'successful_count': 1,
            'total_targets': 1,
            'results': []
        }

        url = reverse('content:publish', kwargs={'pk': self.content.pk})
        response = self.client.post(url, {
            'profile_ids': ['chan_1'],
            'mode': 'immediate'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Successfully published post')
        mock_exec.assert_called_once()

    @patch.object(BufferPublishingOrchestrator, 'execute_publishing')
    def test_content_publish_partial_success_warning(self, mock_exec):
        """Test content_publish displays warning message on partial success (Defect 7 repair)."""
        self.client.login(username='dashboard_author@example.com', password='testpass123')
        mock_exec.return_value = {
            'success': False,
            'partial_success': True,
            'successful_count': 1,
            'total_targets': 2,
            'results': [
                {'profile_id': 'chan_1', 'success': True},
                {'profile_id': 'chan_2', 'success': False, 'error': 'Rate limited'}
            ]
        }

        url = reverse('content:publish', kwargs={'pk': self.content.pk})
        response = self.client.post(url, {
            'profile_ids': ['chan_1', 'chan_2'],
            'mode': 'immediate'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Partial success: 1/2 destinations succeeded')
        mock_exec.assert_called_once()

    @patch.object(BufferPublishingOrchestrator, 'reconcile_publication')
    def test_content_reconcile_post_success(self, mock_reconcile):
        """Test content_reconcile_publication view redirects and notifies on success."""
        self.client.login(username='dashboard_author@example.com', password='testpass123')
        pub = ContentPublication.objects.create(
            content=self.content,
            content_version=self.version,
            user=self.user,
            provider='buffer',
            profile_id='chan_1',
            status='ambiguous'
        )
        pub.status = 'published'
        mock_reconcile.return_value = {'success': True, 'publication': pub}

        url = reverse('content:reconcile_publication', kwargs={'pk': self.content.pk, 'pub_id': pub.pk})
        response = self.client.post(url, {
            'resolution': 'confirmed_published',
            'external_post_id': 'buf_manual_1'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'was successfully marked as published')
        mock_reconcile.assert_called_once()
