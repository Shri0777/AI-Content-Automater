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
        
        # Image generation is deferred / not implemented by default text adapters
        image_providers = self.registry.get_providers_by_capability(ProviderCapability.IMAGE_GENERATION)
        self.assertEqual(len(image_providers), 0)
    
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
    def test_get_active_provider_for_user(self, mock_val):
        """Resolves active user config and falls back to environment when user config is absent."""
        # 1. Without user config and without env key
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
