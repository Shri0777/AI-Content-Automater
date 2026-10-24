"""
Tests for Cloudflare R2 media storage configuration.

These tests verify:
1. Local development storage is the default when R2 is not configured.
2. R2 storage settings are applied when all R2 env vars are present.
3. Media URLs are public HTTPS URLs when R2 is configured.
4. Missing or malformed R2 configuration falls back gracefully.
5. Buffer image URL validation enforces security rules (HTTPS, global routing, SSRF protection).
6. Image MIME type validation accepts valid images and rejects non-images.
7. Storage upload failure is handled gracefully with sanitized error messages.
8. Missing public media configuration fails closed in Buffer publishing.

External storage and Buffer APIs are mocked. No real publishing occurs.
"""
import os
from unittest.mock import patch, MagicMock

import socket

from django.test import TestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from content.services.buffer_service import BufferPublishingService


class R2StorageConfigurationTests(TestCase):
    """Tests that verify R2 storage settings are applied correctly."""

    def test_local_storage_is_default_when_r2_not_configured(self):
        """Without R2 env vars, MEDIA_URL should be the local /media/ path."""
        self.assertEqual(settings.MEDIA_URL, '/media/')

    def test_r2_configured_flag_is_false_without_all_env_vars(self):
        """R2 is only considered configured when every required env var is set."""
        from content_automater.settings.base import _R2_CONFIGURED
        self.assertFalse(_R2_CONFIGURED)

    def test_r2_configured_flag_is_true_when_all_env_vars_set(self):
        """When all R2 env vars and MEDIA_STORAGE=r2 are set, R2 is configured."""
        from content_automater.settings import base as settings_base

        # Temporarily set all required env vars and re-check the flag.
        original_env = {}
        for name in [
            'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY',
            'R2_BUCKET_NAME', 'R2_PUBLIC_DOMAIN', 'MEDIA_STORAGE',
        ]:
            original_env[name] = os.environ.get(name)

        try:
            os.environ['R2_ACCOUNT_ID'] = 'test-account'
            os.environ['R2_ACCESS_KEY_ID'] = 'test-key'
            os.environ['R2_SECRET_ACCESS_KEY'] = 'test-secret'
            os.environ['R2_BUCKET_NAME'] = 'test-bucket'
            os.environ['R2_PUBLIC_DOMAIN'] = 'media.example.com'
            os.environ['MEDIA_STORAGE'] = 'r2'

            # Re-import to re-run module-level config logic.
            import importlib
            importlib.reload(settings_base)
            self.assertTrue(settings_base._R2_CONFIGURED)
            self.assertEqual(settings_base.MEDIA_URL, 'https://media.example.com/')
        finally:
            for name, value in original_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

            importlib.reload(settings_base)


class BufferImageURLValidationTests(TestCase):
    """Tests that Buffer's image URL validation enforces security rules."""

    def setUp(self):
        self.service = BufferPublishingService(access_token='test-token')

    @patch('content.services.buffer_service.socket.getaddrinfo',
           return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))])
    def test_https_url_with_global_host_passes_validation(self, mock_getaddrinfo):
        """A public HTTPS URL with a globally routable host passes."""
        with patch.object(self.service, '_is_reachable_image_url', return_value=True):
            self.assertTrue(self.service._is_public_https_url('https://cdn.example.com/image.png'))

    def test_http_url_is_rejected(self):
        """Non-HTTPS URLs are rejected."""
        self.assertFalse(self.service._is_public_https_url('http://cdn.example.com/image.png'))

    def test_localhost_url_is_rejected(self):
        """localhost URLs cannot reach private addresses."""
        self.assertFalse(self.service._is_public_https_url('https://localhost/image.png'))

    def test_127_0_0_1_url_is_rejected(self):
        """Loopback addresses are rejected (SSRF protection)."""
        self.assertFalse(self.service._is_public_https_url('https://127.0.0.1/image.png'))

    def test_private_range_url_is_rejected(self):
        """Private IP ranges (10.x, 192.168.x) are rejected."""
        self.assertFalse(self.service._is_public_https_url('https://10.0.0.1/image.png'))
        self.assertFalse(self.service._is_public_https_url('https://192.168.1.1/image.png'))

    def test_link_local_url_is_rejected(self):
        """Link-local addresses (169.254.x) are rejected."""
        self.assertFalse(self.service._is_public_https_url('https://169.254.169.254/image.png'))

    def test_url_with_credentials_is_rejected(self):
        """URLs with username/password are rejected."""
        self.assertFalse(self.service._is_public_https_url('https://user:pass@example.com/image.png'))

    def test_empty_url_is_rejected(self):
        """Empty strings and None are rejected."""
        self.assertFalse(self.service._is_public_https_url(''))
        self.assertFalse(self.service._is_public_https_url(None))


class BufferReachableImageValidationTests(TestCase):
    """Tests that Buffer verifies the fetched resource is actually an image."""

    def setUp(self):
        self.service = BufferPublishingService(access_token='test-token')

    def test_valid_image_response_passes(self):
        """HEAD response 200 with image/* content type passes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'image/png'}
        with patch('content.services.buffer_service.requests.head', return_value=mock_response):
            self.assertTrue(self.service._is_reachable_image_url('https://cdn.example.com/image.png'))

    def test_non_200_response_fails(self):
        """HEAD response other than 200 fails."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        with patch('content.services.buffer_service.requests.head', return_value=mock_response):
            self.assertFalse(self.service._is_reachable_image_url('https://cdn.example.com/image.png'))

    def test_non_image_content_type_fails(self):
        """HEAD response with non-image content type fails."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/html'}
        with patch('content.services.buffer_service.requests.head', return_value=mock_response):
            self.assertFalse(self.service._is_reachable_image_url('https://cdn.example.com/image.png'))

    def test_network_error_fails(self):
        """Network errors during HEAD request fail safely."""
        with patch('content.services.buffer_service.requests.head',
                   side_effect=Exception('Network error')):
            self.assertFalse(self.service._is_reachable_image_url('https://cdn.example.com/image.png'))


class StorageUploadFailureTests(TestCase):
    """Tests that storage upload failures are handled gracefully."""

    def test_image_generation_storage_error_is_sanitized(self):
        """ImageGenerationService returns a sanitized error when storage fails."""
        from content.services.image_generation_service import ImageGenerationService
        from content.models import Content, Media
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username='storage-test-user', password='test-password')
        content = Content.objects.create(
            owner=user,
            title='Storage test',
            topic='Test',
            lifecycle_state='draft',
        )

        # Mock a successful provider result so we reach the storage save step.
        mock_adapter = MagicMock()
        mock_adapter.provider_name = 'TestProvider'
        mock_adapter.display_name = 'Test Provider'
        mock_adapter.supported_capabilities = []
        from ai_providers.services.base_adapter import ProviderCapability
        mock_adapter.supported_capabilities = [ProviderCapability.IMAGE_GENERATION]
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content = MagicMock()
        mock_result.content.format = 'PNG'
        mock_result.content.size = (100, 100)
        mock_result.model_used = 'test-model'
        mock_result.metadata = {}
        mock_adapter.generate_image.return_value = mock_result

        with patch('content.services.image_generation_service.CredentialValidationService.get_active_provider_for_user',
                   return_value=(mock_adapter, 'test-credential', 'test-model', 'https://endpoint')), \
             patch('content.services.image_generation_service.Media.objects.create') as mock_create:
            # Simulate storage failure during file save
            mock_create.side_effect = Exception('Storage backend unavailable')

            result = ImageGenerationService.generate_image_for_content(
                content_id=content.pk,
                user=user,
                prompt='A test image.',
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'storage_error')
        # Error message must not expose raw exception details
        self.assertNotIn('Storage backend unavailable', result['error'])


class StorageMissingConfigTests(TestCase):
    """Tests for missing or malformed public media configuration."""

    def test_no_public_media_url_fails_closed(self):
        """submit_to_buffer fails closed when media URL is not public HTTPS."""
        from content.models import Campaign, Content, ContentVersion, ContentReview, CampaignExecution, Media
        from content.services.automated_post_orchestration import AutomatedPostOrchestrationService
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username='missing-config-user', password='test-password')
        campaign = Campaign.objects.create(
            owner=user,
            name='Missing config campaign',
            topic='Test',
            generation_instructions='Test.',
            start_date='2026-01-01',
            image_approval_required=True,
            target_platforms=['buffer-channel-1'],
        )
        content = Content.objects.create(
            owner=user,
            title='Missing config',
            topic='Test',
            lifecycle_state='pending_review',
        )
        version = ContentVersion.create_initial_version(
            content, user, 'A reviewed post with enough text content.',
        )
        content.current_version = version
        content.save(update_fields=['current_version'])
        ContentReview.objects.create(content_version=version, status='passed', summary='Passed.')
        execution = CampaignExecution.objects.create(
            campaign=campaign,
            content=content,
            execution_key='missing-config-execution',
            scheduled_time=content.created_at,
            status='completed',
            execution_data={'image_version_id': version.pk},
        )
        media = Media.objects.create(
            owner=user,
            content=content,
            file_name='test.png',
            file_size=100,
            mime_type='image/png',
            is_validated=True,
            approval_status='approved',
        )
        execution.image_media = media
        execution.save(update_fields=['image_media'])
        version.is_approved = True
        version.save(update_fields=['is_approved'])
        content.lifecycle_state = 'approved'
        content.save(update_fields=['lifecycle_state'])

        # Use local media (relative URL, not public HTTPS)
        with patch('content.services.buffer_service.BufferPublishingService.get_profiles',
                   return_value=[{'id': 'buffer-channel-1', 'service': 'linkedin'}]), \
             patch('content.services.publishing_service.PublishingPreparationService.prepare_content',
                   return_value={'success': True}), \
             patch('content.services.publishing_orchestrator.BufferPublishingOrchestrator.execute_publishing') as publish:
            result = AutomatedPostOrchestrationService.submit_to_buffer(execution.pk)

        self.assertEqual(result['error_type'], 'public_media_url_required')
        publish.assert_not_called()
