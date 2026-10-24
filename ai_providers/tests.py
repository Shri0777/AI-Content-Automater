"""
Comprehensive test suite for AI provider integration (Phase 3).

Covers:
- Provider registry and selection
- Successful and failed credential validation
- Ambiguous and unsupported provider configurations
- Model availability and capability checks
- Timeouts, rate limits, quota failures, and malformed responses
- Secret masking and non-disclosure
- Credential ownership and authorization (IDOR prevention)
- Safe endpoint validation and SSRF protections
- Text-generation adapter success, failures, and bounded retries
- Dashboard form validation, credential preservation, and HTMX responses
"""
import socket
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ai_providers.models import ProviderConfig, ProviderCredential
from ai_providers.services.anthropic_adapter import AnthropicAdapter
from ai_providers.services.base_adapter import (
    GenerationRequest,
    ProviderCapability,
    ProviderErrorType,
)
from ai_providers.services.openai_adapter import OpenAIAdapter
from ai_providers.services.registry import ProviderRegistry, registry
from ai_providers.services.security import validate_safe_endpoint
from ai_providers.services.validation_service import CredentialValidationService

User = get_user_model()


class ProviderRegistryTests(TestCase):
    """Tests for ProviderRegistry discovery and lookups."""

    def setUp(self):
        self.registry = ProviderRegistry.get_instance()

    def test_registry_singleton(self):
        """Ensure ProviderRegistry follows singleton pattern."""
        reg1 = ProviderRegistry.get_instance()
        reg2 = ProviderRegistry.get_instance()
        self.assertIs(reg1, reg2)

    def test_default_providers_registered(self):
        """Ensure OpenAI and Anthropic adapters are registered by default."""
        openai_adapter = self.registry.get_provider('openai')
        anthropic_adapter = self.registry.get_provider('anthropic')
        self.assertIsNotNone(openai_adapter)
        self.assertIsNotNone(anthropic_adapter)
        self.assertEqual(openai_adapter.provider_name, 'openai')
        self.assertEqual(anthropic_adapter.provider_name, 'anthropic')

    def test_case_insensitive_lookup(self):
        """Lookup by provider name should be case-insensitive."""
        self.assertIsNotNone(self.registry.get_provider('OpenAI'))
        self.assertIsNotNone(self.registry.get_provider('OPENAI'))
        self.assertIsNotNone(self.registry.get_provider('anthropic'))
        self.assertIsNone(self.registry.get_provider('non_existent_provider'))

    def test_providers_by_capability(self):
        """Filter registered adapters by capability."""
        text_providers = self.registry.get_providers_by_capability(ProviderCapability.TEXT_GENERATION)
        provider_names = [p.provider_name for p in text_providers]
        self.assertIn('openai', provider_names)
        self.assertIn('anthropic', provider_names)

        # Image generation now includes NVIDIA FLUX adapter
        image_providers = self.registry.get_providers_by_capability(ProviderCapability.IMAGE_GENERATION)
        self.assertEqual(len(image_providers), 1)
        self.assertEqual(image_providers[0].provider_name, 'nvidia_flux')

    @override_settings(TEXT_API_KEY='test-env-key-123', TEXT_PROVIDER='openai')
    def test_environment_provider_explicit(self):
        """Detect environment provider when TEXT_PROVIDER is explicitly set."""
        env_prov = self.registry.get_environment_text_provider()
        self.assertIsNotNone(env_prov)
        adapter, key, model, endpoint = env_prov
        self.assertEqual(adapter.provider_name, 'openai')
        self.assertEqual(key, 'test-env-key-123')

    @override_settings(TEXT_API_KEY='', TEXT_PROVIDER='auto')
    def test_environment_provider_missing(self):
        """Return None when TEXT_API_KEY is not set."""
        self.assertIsNone(self.registry.get_environment_text_provider())


class SSRFSecurityTests(TestCase):
    """Tests for safe endpoint validation and SSRF defenses."""

    def test_public_https_endpoint_allowed(self):
        """Standard public HTTPS endpoints must be permitted."""
        is_safe, reason = validate_safe_endpoint('https://api.openai.com/v1')
        self.assertTrue(is_safe, f"Valid HTTPS URL rejected: {reason}")

        is_safe, reason = validate_safe_endpoint('https://api.anthropic.com/v1')
        self.assertTrue(is_safe, f"Valid HTTPS URL rejected: {reason}")

    def test_insecure_http_scheme_rejected(self):
        """Plain HTTP URLs must be rejected by default."""
        is_safe, reason = validate_safe_endpoint('http://api.openai.com/v1')
        self.assertFalse(is_safe)
        self.assertIn("Only HTTPS is permitted", reason)

    def test_embedded_credentials_rejected(self):
        """URLs containing credentials must be rejected."""
        is_safe, reason = validate_safe_endpoint('https://user:pass@api.openai.com/v1')
        self.assertFalse(is_safe)
        self.assertIn("Embedded credentials", reason)

    def test_localhost_and_loopback_rejected(self):
        """Localhost and loopback IPs must be blocked."""
        is_safe, reason = validate_safe_endpoint('https://localhost:8000')
        self.assertFalse(is_safe)

        is_safe, reason = validate_safe_endpoint('https://127.0.0.1:8000')
        self.assertFalse(is_safe)

    def test_cloud_metadata_and_link_local_rejected(self):
        """AWS/GCP/Azure link-local metadata endpoints must be blocked."""
        is_safe, reason = validate_safe_endpoint('https://169.254.169.254/latest/meta-data/')
        self.assertFalse(is_safe)

        is_safe, reason = validate_safe_endpoint('https://metadata.google.internal/computeMetadata/v1/')
        self.assertFalse(is_safe)

    @patch('socket.getaddrinfo')
    def test_private_subnets_blocked(self, mock_getaddrinfo):
        """Private subnets (10.x, 172.16.x, 192.168.x) must be blocked upon resolution."""
        # Mock DNS resolution to a private RFC 1918 address
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.50', 443))
        ]
        is_safe, reason = validate_safe_endpoint('https://internal-ai-service.com')
        self.assertFalse(is_safe)
        self.assertIn("private network address", reason)


class CredentialEncryptionAndMaskingTests(TestCase):
    """Tests for secure credential encryption and secret masking."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='password123')
        self.config = ProviderConfig.objects.create(
            user=self.user,
            provider_name='openai',
            capability='text'
        )

    def test_credential_encryption_at_rest(self):
        """Credential must be stored encrypted in the database as binary ciphertext."""
        cred = ProviderCredential(config=self.config, credential_name='api_key', is_active=True)
        raw_key = 'sk-proj-super-secret-production-key-998877'
        cred.set_credential(raw_key)
        cred.save()

        # Reload directly from database
        reloaded = ProviderCredential.objects.get(pk=cred.pk)
        self.assertNotEqual(bytes(reloaded.encrypted_value), raw_key.encode('utf-8'))
        self.assertNotIn(raw_key.encode('utf-8'), bytes(reloaded.encrypted_value))

        # Decryption returns the exact plaintext key
        self.assertEqual(reloaded.get_credential(), raw_key)

    def test_credential_masking(self):
        """Masked value must reveal only safe prefix/suffix or dots, never full secret."""
        cred = ProviderCredential(config=self.config, credential_name='api_key', is_active=True)

        # Long key (typical API key)
        cred.set_credential('sk-proj-1234567890abcdef')
        masked = cred.get_masked_value()
        self.assertTrue(masked.startswith('sk-p'))
        self.assertTrue(masked.endswith('cdef'))
        self.assertIn('••••••••', masked)
        self.assertNotIn('1234567890', masked)

        # Short key
        cred.set_credential('shortkey')
        self.assertEqual(cred.get_masked_value(), '••••••••')

    def test_credential_deactivates_older(self):
        """Creating an active credential deactivates previously active ones for that config."""
        c1 = ProviderCredential(config=self.config, credential_name='api_key', is_active=True)
        c1.set_credential('key-one')
        c1.save()

        c2 = ProviderCredential(config=self.config, credential_name='api_key', is_active=True)
        c2.set_credential('key-two')
        c2.save()

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_active)
        self.assertTrue(c2.is_active)


class OpenAIAdapterContractTests(TestCase):
    """Tests for OpenAIAdapter methods, error mappings, and bounded retries."""

    def setUp(self):
        self.adapter = OpenAIAdapter()

    @patch('requests.get')
    def test_validation_success(self, mock_get):
        """Successful validation returns validated status and available model."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'data': [{'id': 'gpt-4o-mini'}, {'id': 'gpt-4o'}]}
        )

        result = self.adapter.validate_credential(
            credential='test-key',
            model_name='gpt-4o-mini',
            capability=ProviderCapability.TEXT_GENERATION
        )
        self.assertTrue(result.success)
        self.assertEqual(result.provider_identified, 'openai')
        self.assertEqual(result.model_available, 'gpt-4o-mini')

    @patch('requests.get')
    def test_validation_invalid_auth(self, mock_get):
        """HTTP 401 maps to INVALID_CREDENTIAL error."""
        mock_get.return_value = MagicMock(status_code=401)
        result = self.adapter.validate_credential(credential='bad-key')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.INVALID_CREDENTIAL)

    @patch('requests.get')
    def test_validation_rate_limited(self, mock_get):
        """HTTP 429 maps to RATE_LIMITED error."""
        mock_get.return_value = MagicMock(status_code=429)
        result = self.adapter.validate_credential(credential='key')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.RATE_LIMITED)

    @patch('requests.get')
    def test_validation_quota_exceeded(self, mock_get):
        """HTTP 403 maps to QUOTA_EXCEEDED error."""
        mock_get.return_value = MagicMock(status_code=403)
        result = self.adapter.validate_credential(credential='key')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.QUOTA_EXCEEDED)

    @patch('requests.get')
    def test_validation_model_unavailable(self, mock_get):
        """Requesting unavailable model maps to MODEL_UNAVAILABLE."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'data': [{'id': 'gpt-3.5-turbo'}]}
        )
        result = self.adapter.validate_credential(
            credential='test-key',
            model_name='gpt-4o-custom'
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.MODEL_UNAVAILABLE)

    def test_validation_unsupported_capability(self):
        """Checking unsupported capability fails without making network calls."""
        result = self.adapter.validate_credential(
            credential='test-key',
            capability=ProviderCapability.IMAGE_GENERATION
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.LACKS_CAPABILITY)

    @patch('requests.post')
    def test_generate_text_success(self, mock_post):
        """Successful text generation returns normalized GenerationResult."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'model': 'gpt-4o-mini',
                'choices': [{'message': {'content': 'Generated portfolio draft.'}, 'finish_reason': 'stop'}],
                'usage': {'total_tokens': 42}
            }
        )

        req = GenerationRequest(
            prompt="Write a post about automated testing.",
            system_prompt="You are a senior tech writer."
        )
        res = self.adapter.generate_text(req, credential='test-key')
        self.assertTrue(res.success)
        self.assertEqual(res.content, 'Generated portfolio draft.')
        self.assertEqual(res.tokens_used, 42)
        self.assertEqual(res.model_used, 'gpt-4o-mini')

    @patch('requests.post')
    def test_generate_text_transient_retry(self, mock_post):
        """Adapter performs bounded retries on 503 transient error."""
        # First call fails with 503, second call succeeds with 200
        mock_post.side_effect = [
            MagicMock(status_code=503, text="Service Unavailable"),
            MagicMock(
                status_code=200,
                json=lambda: {
                    'choices': [{'message': {'content': 'Recovered response'}}],
                    'usage': {'total_tokens': 10}
                }
            )
        ]

        res = self.adapter.generate_text("Prompt", credential='key')
        self.assertTrue(res.success)
        self.assertEqual(res.content, 'Recovered response')
        self.assertEqual(mock_post.call_count, 2)


class AnthropicAdapterContractTests(TestCase):
    """Tests for AnthropicAdapter contract and error handling."""

    def setUp(self):
        self.adapter = AnthropicAdapter()

    @patch('requests.get')
    def test_validation_success(self, mock_get):
        """Anthropic validation succeeds when models probe returns 200."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'data': [{'id': 'claude-3-5-sonnet-20241022'}]}
        )
        result = self.adapter.validate_credential(credential='anthropic-key')
        self.assertTrue(result.success)
        self.assertEqual(result.provider_identified, 'anthropic')

    @patch('requests.post')
    def test_generate_text_success(self, mock_post):
        """Anthropic generation extracts text content and token usage."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'model': 'claude-3-5-sonnet-20241022',
                'content': [{'type': 'text', 'text': 'Claude generated response'}],
                'usage': {'input_tokens': 15, 'output_tokens': 25}
            }
        )

        res = self.adapter.generate_text("Prompt", credential='key')
        self.assertTrue(res.success)
        self.assertEqual(res.content, 'Claude generated response')
        self.assertEqual(res.tokens_used, 40)


class CredentialValidationServiceTests(TestCase):
    """Tests for the validation orchestrator and credential persistence."""

    def setUp(self):
        self.user = User.objects.create_user(username='bob', password='password123')

    @patch.object(OpenAIAdapter, 'validate_credential')
    def test_validate_and_save_success(self, mock_val):
        """Successful validation creates ProviderConfig and encrypted ProviderCredential."""
        from ai_providers.services.base_adapter import ValidationResult
        mock_val.return_value = ValidationResult(success=True, message="OK", capabilities=["text"])

        res = CredentialValidationService.validate_and_save(
            user=self.user,
            credential_value='sk-test-valid-key',
            capability='text',
            provider_name='openai',
            model_name='gpt-4o-mini'
        )

        self.assertTrue(res['success'])
        config = ProviderConfig.objects.get(user=self.user, provider_name='openai')
        self.assertEqual(config.validation_status, 'success')
        self.assertIsNotNone(config.get_active_credential())
        self.assertEqual(config.get_active_credential().get_credential(), 'sk-test-valid-key')

    @patch.object(OpenAIAdapter, 'validate_credential')
    def test_empty_credential_preserves_existing(self, mock_val):
        """Submitting an empty credential when updating an existing config keeps the existing key."""
        from ai_providers.services.base_adapter import ValidationResult
        mock_val.return_value = ValidationResult(success=True, message="OK", capabilities=["text"])

        # Initial save
        res1 = CredentialValidationService.validate_and_save(
            user=self.user,
            credential_value='sk-original-key',
            capability='text',
            provider_name='openai'
        )
        self.assertTrue(res1['success'])
        config = ProviderConfig.objects.get(pk=res1['config_id'])

        # Update without providing key
        res2 = CredentialValidationService.validate_and_save(
            user=self.user,
            credential_value='',  # Empty string
            capability='text',
            provider_name='openai',
            model_name='gpt-4o',
            config_id=config.pk
        )
        self.assertTrue(res2['success'])
        config.refresh_from_db()
        self.assertEqual(config.model_name, 'gpt-4o')
        # Original credential was preserved
        self.assertEqual(config.get_active_credential().get_credential(), 'sk-original-key')

    @patch.object(OpenAIAdapter, 'validate_credential')
    @override_settings(TEXT_API_KEY='', TEXT_PROVIDER='', TEXT_API_BASE_URL='', TEXT_MODEL='')
    def test_get_active_provider_for_user(self, mock_val):
        """Resolves active user config and falls back to environment when user config is absent."""
        # 1. Without user config and without env key (environment vars mocked to empty)
        adapter, cred, model, ep = CredentialValidationService.get_active_provider_for_user(self.user)
        self.assertIsNone(adapter)

        # 2. With user config
        config = ProviderConfig.objects.create(
            user=self.user,
            provider_name='openai',
            capability='text',
            is_active=True,
            model_name='gpt-4o'
        )
        c = ProviderCredential(config=config, credential_name='api_key', is_active=True)
        c.set_credential('my-user-key')
        c.save()

        adapter, cred, model, ep = CredentialValidationService.get_active_provider_for_user(self.user)
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.provider_name, 'openai')
        self.assertEqual(cred, 'my-user-key')
        self.assertEqual(model, 'gpt-4o')


class ProviderViewsDashboardAndSecurityTests(TestCase):
    """Tests for dashboard views, authorization, secret non-disclosure, and HTMX endpoints."""

    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='user_a@example.com', email='user_a@example.com', password='password123')
        self.user_b = User.objects.create_user(username='user_b@example.com', email='user_b@example.com', password='password123')

        self.config_a = ProviderConfig.objects.create(
            user=self.user_a,
            provider_name='openai',
            capability='text',
            is_active=True,
            validation_status='success',
            validation_message='Ready'
        )
        self.cred_a = ProviderCredential(config=self.config_a, credential_name='api_key', is_active=True)
        self.cred_a.set_credential('sk-user-a-super-secret-key-12345')
        self.cred_a.save()

    def test_dashboard_requires_login(self):
        """Unauthenticated access redirects to login."""
        response = self.client.get(reverse('ai_providers:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_masks_secret(self):
        """Dashboard displays masked credential and never renders plaintext key."""
        self.client.login(username='user_a@example.com', password='password123')
        response = self.client.get(reverse('ai_providers:dashboard'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        # Plaintext key MUST NOT appear anywhere in rendered HTML
        self.assertNotIn('sk-user-a-super-secret-key-12345', content)
        # Masked representation should appear
        self.assertIn('••••••••', content)

    def test_cross_user_isolation_on_validate(self):
        """User B cannot validate User A's provider configuration (IDOR prevention)."""
        self.client.login(username='user_b@example.com', password='password123')
        response = self.client.post(reverse('ai_providers:validate', args=[self.config_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cross_user_isolation_on_remove(self):
        """User B cannot remove User A's provider configuration."""
        self.client.login(username='user_b@example.com', password='password123')
        response = self.client.post(reverse('ai_providers:remove', args=[self.config_a.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProviderConfig.objects.filter(pk=self.config_a.pk).exists())

    @patch.object(OpenAIAdapter, 'validate_credential')
    def test_validate_config_htmx_partial(self, mock_val):
        """HTMX request to validate endpoint returns partial status snippet."""
        from ai_providers.services.base_adapter import ValidationResult
        mock_val.return_value = ValidationResult(success=True, message="Re-validated cleanly")

        self.client.login(username='user_a@example.com', password='password123')
        response = self.client.post(
            reverse('ai_providers:validate', args=[self.config_a.pk]),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ai_providers/partials/status.html')
        self.assertContains(response, 'Re-validated cleanly')

    @patch.object(OpenAIAdapter, 'validate_credential')
    def test_configure_post_saves_and_redirects(self, mock_val):
        """POST to configure creates config and redirects to dashboard with success message."""
        from ai_providers.services.base_adapter import ValidationResult
        mock_val.return_value = ValidationResult(success=True, message="Validated successfully")

        self.client.login(username='user_b@example.com', password='password123')
        response = self.client.post(reverse('ai_providers:configure'), {
            'capability': 'text',
            'provider': 'openai',
            'credential': 'sk-user-b-key-999',
            'model_name': 'gpt-4o-mini'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('ai_providers:dashboard'))

        # Verify saved
        b_config = ProviderConfig.objects.filter(user=self.user_b, provider_name='openai').first()
        self.assertIsNotNone(b_config)
        self.assertEqual(b_config.get_active_credential().get_credential(), 'sk-user-b-key-999')


class NVIDIATextAdapterTests(TestCase):
    """Test NVIDIA text adapter (OpenAI-compatible endpoint)."""

    def setUp(self):
        self.adapter = NVIDIAAdapter()

    def test_provider_properties(self):
        """NVIDIA text adapter has correct provider identity."""
        self.assertEqual(self.adapter.provider_name, 'nvidia')
        self.assertEqual(self.adapter.display_name, 'NVIDIA NIM')
        self.assertIn(ProviderCapability.TEXT_GENERATION, self.adapter.supported_capabilities)
        self.assertEqual(self.adapter.default_endpoint, 'https://integrate.api.nvidia.com/v1')

    @patch('ai_providers.services.openai_adapter.requests.get')
    def test_identify_provider_with_nvidia_endpoint(self, mock_get):
        """Identification succeeds when credential works with NVIDIA endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'qwen/qwen3-235b-a22b'},
                {'id': 'openai/gpt-oss-20b'}
            ]
        }
        mock_get.return_value = mock_response

        result = self.adapter.identify_provider('nvapi-test123')
        self.assertTrue(result)

    @patch('ai_providers.services.openai_adapter.requests.get')
    def test_validate_credential_success(self, mock_get):
        """Validation succeeds with valid NVIDIA credential."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'qwen/qwen3-235b-a22b'},
                {'id': 'openai/gpt-oss-20b'}
            ]
        }
        mock_get.return_value = mock_response

        result = self.adapter.validate_credential(
            'nvapi-test123',
            model_name='openai/gpt-oss-20b'
        )
        self.assertTrue(result.success)
        # NVIDIA adapter inherits from OpenAI, so provider_identified is 'openai'
        self.assertIn(result.provider_identified, ['openai', 'nvidia'])

    @patch('ai_providers.services.openai_adapter.requests.post')
    def test_generate_text_with_nvidia_model(self, mock_post):
        """Text generation works with NVIDIA-specific model."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Generated text'}, 'finish_reason': 'stop'}],
            'model': 'openai/gpt-oss-20b',
            'usage': {'total_tokens': 50}
        }
        mock_post.return_value = mock_response

        request = GenerationRequest(
            prompt='Test prompt',
            model_name='openai/gpt-oss-20b'
        )
        result = self.adapter.generate_text(request, 'nvapi-test123')

        self.assertTrue(result.success)
        self.assertEqual(result.content, 'Generated text')
        self.assertEqual(result.model_used, 'openai/gpt-oss-20b')


class NVIDIAFluxAdapterTests(TestCase):
    """Test NVIDIA FLUX image generation adapter."""

    def setUp(self):
        from ai_providers.services.nvidia_flux_adapter import NVIDIAFluxAdapter
        self.adapter = NVIDIAFluxAdapter()

    def test_provider_properties(self):
        """NVIDIA FLUX adapter has correct provider identity."""
        self.assertEqual(self.adapter.provider_name, 'nvidia_flux')
        self.assertEqual(self.adapter.display_name, 'NVIDIA FLUX')
        self.assertIn(ProviderCapability.IMAGE_GENERATION, self.adapter.supported_capabilities)
        self.assertEqual(self.adapter.default_model, 'black-forest-labs/flux-3-image-klein')

    def test_text_generation_not_supported(self):
        """FLUX adapter correctly rejects text generation requests."""
        result = self.adapter.generate_text('test prompt', 'nvapi-123')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.LACKS_CAPABILITY)

    @patch('ai_providers.services.nvidia_flux_adapter.requests.get')
    def test_validate_credential_success(self, mock_get):
        """Validation succeeds with valid NVIDIA API key."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'id': 'black-forest-labs/flux-3-image-klein'}
            ]
        }
        mock_get.return_value = mock_response

        result = self.adapter.validate_credential('nvapi-test123')
        self.assertTrue(result.success)
        self.assertIn('image', result.capabilities)

    @patch('ai_providers.services.nvidia_flux_adapter.requests.get')
    def test_validate_credential_missing(self, mock_get):
        """Validation fails with empty credential."""
        result = self.adapter.validate_credential('')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.MISSING_CREDENTIAL)

    @patch('ai_providers.services.nvidia_flux_adapter.requests.get')
    def test_validate_credential_unauthorized(self, mock_get):
        """Validation fails with 401 response."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.adapter.validate_credential('invalid-key')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.INVALID_CREDENTIAL)

    @patch('ai_providers.services.nvidia_flux_adapter.requests.post')
    def test_generate_image_with_url_response(self, mock_post):
        """Image generation succeeds with URL response."""
        # Mock successful generation response
        mock_gen_response = Mock()
        mock_gen_response.status_code = 200
        mock_gen_response.json.return_value = {
            'data': [{
                'url': 'https://api.nvidia.com/images/test123.png',
                'revised_prompt': 'Enhanced prompt'
            }],
            'model': 'black-forest-labs/flux-3-image-klein'
        }

        # Mock image download
        from PIL import Image
        import io
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        mock_download_response = Mock()
        mock_download_response.status_code = 200
        mock_download_response.headers = {'content-type': 'image/png'}
        mock_download_response.iter_content = lambda chunk_size: [img_bytes.read()]

        with patch('ai_providers.services.nvidia_flux_adapter.requests.get', return_value=mock_download_response):
            mock_post.return_value = mock_gen_response

            result = self.adapter.generate_image(
                'A beautiful landscape',
                'nvapi-test123'
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.content)
            self.assertEqual(result.model_used, 'black-forest-labs/flux-3-image-klein')

    @patch('ai_providers.services.nvidia_flux_adapter.requests.post')
    def test_generate_image_empty_prompt(self, mock_post):
        """Image generation fails with empty prompt."""
        result = self.adapter.generate_image('', 'nvapi-test123')
        self.assertFalse(result.success)
        self.assertIn('empty', result.error.lower())

    @patch('ai_providers.services.nvidia_flux_adapter.requests.post')
    def test_generate_image_rate_limit(self, mock_post):
        """Image generation handles rate limiting."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        result = self.adapter.generate_image('Test prompt', 'nvapi-test123')
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, ProviderErrorType.RATE_LIMITED)


class ProviderRegistryImageTests(TestCase):
    """Test provider registry with image providers."""

    def setUp(self):
        from ai_providers.services.registry import ProviderRegistry
        self.registry = ProviderRegistry()

    def test_nvidia_flux_registered(self):
        """NVIDIA FLUX adapter is registered."""
        adapter = self.registry.get_provider('nvidia_flux')
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.provider_name, 'nvidia_flux')

    def test_get_image_providers(self):
        """Registry returns image-capable providers."""
        providers = self.registry.get_providers_by_capability(ProviderCapability.IMAGE_GENERATION)
        self.assertTrue(len(providers) > 0)

        flux_found = any(p.provider_name == 'nvidia_flux' for p in providers)
        self.assertTrue(flux_found)

    @patch('ai_providers.services.registry.settings')
    def test_environment_image_provider_resolution(self, mock_settings):
        """Registry resolves image provider from environment."""
        mock_settings.IMAGE_API_KEY = 'nvapi-test123'
        mock_settings.IMAGE_PROVIDER = 'nvidia_flux'
        mock_settings.IMAGE_MODEL = 'black-forest-labs/flux-3-image-klein'

        result = self.registry.get_environment_image_provider()
        self.assertIsNotNone(result)
        adapter, api_key, model, endpoint = result
        self.assertEqual(adapter.provider_name, 'nvidia_flux')
        self.assertEqual(api_key, 'nvapi-test123')


class ImageGenerationServiceTests(TestCase):
    """Test image generation service."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.content = Content.objects.create(
            owner=self.user,
            title='Test Content',
            topic='Technology',
            lifecycle_state='in_progress'
        )

    def test_validate_prompt_empty(self):
        """Prompt validation rejects empty prompts."""
        from content.services.image_generation_service import ImageGenerationService
        result = ImageGenerationService.validate_image_prompt('')
        self.assertFalse(result['valid'])

    def test_validate_prompt_too_long(self):
        """Prompt validation rejects overly long prompts."""
        from content.services.image_generation_service import ImageGenerationService
        long_prompt = 'x' * 1001
        result = ImageGenerationService.validate_image_prompt(long_prompt)
        self.assertFalse(result['valid'])

    def test_validate_prompt_inappropriate_content(self):
        """Prompt validation rejects inappropriate content."""
        from content.services.image_generation_service import ImageGenerationService
        result = ImageGenerationService.validate_image_prompt('nude person')
        self.assertFalse(result['valid'])
        self.assertIn('inappropriate', result['error'].lower())

    @patch('content.services.image_generation_service.CredentialValidationService.get_active_provider_for_user')
    def test_generate_image_no_provider(self, mock_get_provider):
        """Image generation fails when no provider configured."""
        from content.services.image_generation_service import ImageGenerationService
        mock_get_provider.return_value = (None, None, None, None)

        result = ImageGenerationService.generate_image_for_content(
            self.content.id,
            self.user,
            'A beautiful sunset'
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'no_provider')

    @patch('content.services.image_generation_service.CredentialValidationService.get_active_provider_for_user')
    def test_generate_image_success(self, mock_get_provider):
        """Image generation succeeds and creates Media record."""
        from content.services.image_generation_service import ImageGenerationService
        from ai_providers.services.nvidia_flux_adapter import NVIDIAFluxAdapter
        from ai_providers.services.base_adapter import GenerationResult
        from PIL import Image

        # Create test image
        test_image = Image.new('RGB', (512, 512), color='blue')

        # Mock adapter
        adapter = NVIDIAFluxAdapter()
        mock_get_provider.return_value = (adapter, 'nvapi-test', 'black-forest-labs/flux-3-image-klein', None)

        # Mock generation
        with patch.object(adapter, 'generate_image') as mock_gen:
            mock_gen.return_value = GenerationResult(
                success=True,
                content=test_image,
                model_used='black-forest-labs/flux-3-image-klein',
                metadata={'size': (512, 512), 'format': 'PNG'}
            )

            result = ImageGenerationService.generate_image_for_content(
                self.content.id,
                self.user,
                'A test image prompt'
            )

            self.assertTrue(result['success'])
            self.assertIn('media_id', result)

            # Verify Media record created
            media = Media.objects.get(pk=result['media_id'])
            self.assertEqual(media.owner, self.user)
            self.assertEqual(media.content, self.content)
            self.assertTrue(media.is_validated)
            self.assertEqual(media.width, 512)
            self.assertEqual(media.height, 512)


# Import necessary models for tests
from ai_providers.services.nvidia_adapter import NVIDIAAdapter
from ai_providers.services.base_adapter import (
    GenerationRequest,
    ProviderCapability,
    ProviderErrorType
)
from content.models import Content, Media
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
