"""
Credential validation and resolution service.

Orchestrates provider identification, credential validation, configuration persistence,
and active provider resolution with environment fallback.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone

from ..models import ProviderConfig, ProviderCredential
from .base_adapter import (
    BaseProviderAdapter,
    ProviderCapability,
    ProviderErrorType,
    ValidationResult,
)
from .registry import registry
from .security import validate_safe_endpoint

logger = logging.getLogger(__name__)


class CredentialValidationService:
    """
    Service for validating provider credentials and managing user provider configurations.
    """

    @staticmethod
    def validate_and_save(
        user,
        credential_value: Optional[str],
        capability: str = 'text',
        provider_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        config_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate credential and save configuration if successful.

        If updating an existing configuration and credential_value is empty,
        the existing credential is kept and only configuration metadata is updated.
        """
        cap_enum = (
            ProviderCapability.TEXT_GENERATION if capability == 'text'
            else ProviderCapability.IMAGE_GENERATION
        )

        # Check for existing config
        existing_config = None
        if config_id:
            existing_config = ProviderConfig.objects.filter(pk=config_id, user=user).first()
        elif provider_name:
            existing_config = ProviderConfig.objects.filter(
                user=user,
                provider_name=provider_name,
                capability=capability
            ).first()

        # Check if credential is empty on update
        effective_credential = credential_value
        if not effective_credential or not effective_credential.strip():
            if existing_config:
                cred_obj = existing_config.get_active_credential()
                if cred_obj:
                    effective_credential = cred_obj.get_credential()

            if not effective_credential:
                return {
                    'success': False,
                    'error': 'API key is required to configure a provider.',
                    'error_type': ProviderErrorType.MISSING_CREDENTIAL
                }

        # Step 1: Endpoint validation if provided
        clean_endpoint = endpoint.strip() if endpoint and endpoint.strip() else None
        if clean_endpoint:
            is_safe, reason = validate_safe_endpoint(clean_endpoint)
            if not is_safe:
                return {
                    'success': False,
                    'error': f"Endpoint URL rejected for security: {reason}",
                    'error_type': ProviderErrorType.SSRF_BLOCKED
                }

        # Step 2: Provider identification
        if provider_name and provider_name.strip() and provider_name.strip().lower() != 'auto':
            adapter = registry.get_provider(provider_name.strip().lower())
            if not adapter:
                return {
                    'success': False,
                    'error': f"Unsupported provider: '{provider_name}'. Supported providers: {[p.provider_name for p in registry.get_all_providers()]}",
                    'error_type': ProviderErrorType.UNSUPPORTED_PROVIDER
                }
        else:
            adapter = registry.identify_provider(effective_credential, clean_endpoint)
            if not adapter:
                return {
                    'success': False,
                    'error': "Could not automatically identify provider from credentials. Please select a provider explicitly.",
                    'error_type': ProviderErrorType.AMBIGUOUS_PROVIDER
                }
            provider_name = adapter.provider_name

        # Step 3: Validate credential and capabilities
        clean_model = model_name.strip() if model_name and model_name.strip() else None
        validation = adapter.validate_credential(
            credential=effective_credential,
            endpoint=clean_endpoint,
            model_name=clean_model,
            capability=cap_enum
        )

        if not validation.success:
            return {
                'success': False,
                'error': validation.message,
                'error_type': validation.error_type
            }

        # Step 4: Save configuration and encrypted credential
        try:
            config, created = ProviderConfig.objects.get_or_create(
                user=user,
                provider_name=adapter.provider_name,
                capability=capability,
                defaults={
                    'is_active': True,
                    'endpoint_url': clean_endpoint,
                    'model_name': clean_model or adapter.default_model,
                    'last_validated': timezone.now(),
                    'validation_status': 'success',
                    'validation_message': validation.message
                }
            )

            if not created:
                config.is_active = True
                config.endpoint_url = clean_endpoint
                config.model_name = clean_model or adapter.default_model
                config.last_validated = timezone.now()
                config.validation_status = 'success'
                config.validation_message = validation.message
                config.save()

            # Save or update credential only if a new value was provided
            if credential_value and credential_value.strip():
                credential_obj = ProviderCredential(
                    config=config,
                    credential_name='api_key',
                    is_active=True
                )
                credential_obj.set_credential(credential_value.strip())
                credential_obj.save()

            return {
                'success': True,
                'config_id': config.pk,
                'provider': adapter.provider_name,
                'capability': capability,
                'message': f"{adapter.display_name} validated and configured successfully."
            }

        except Exception as e:
            logger.error(f"Failed to persist provider configuration: {e}")
            return {
                'success': False,
                'error': f"Failed to save configuration securely: {str(e)}",
                'error_type': ProviderErrorType.UNKNOWN
            }

    @staticmethod
    def validate_existing(config: ProviderConfig) -> ValidationResult:
        """
        Re-validate an existing configuration.
        """
        adapter = registry.get_provider(config.provider_name)
        if not adapter:
            result = ValidationResult(
                success=False,
                message=f"Provider '{config.provider_name}' is not registered or supported.",
                error_type=ProviderErrorType.UNSUPPORTED_PROVIDER
            )
            config.last_validated = timezone.now()
            config.validation_status = 'failed'
            config.validation_message = result.message
            config.save()
            return result

        credential_obj = config.get_active_credential()
        if not credential_obj:
            result = ValidationResult(
                success=False,
                message="No active credential found for this configuration.",
                error_type=ProviderErrorType.MISSING_CREDENTIAL
            )
            config.last_validated = timezone.now()
            config.validation_status = 'failed'
            config.validation_message = result.message
            config.save()
            return result

        credential_value = credential_obj.get_credential()
        if not credential_value:
            result = ValidationResult(
                success=False,
                message="Unable to decrypt stored credentials. Key may be invalid or missing.",
                error_type=ProviderErrorType.INVALID_CREDENTIAL
            )
            config.last_validated = timezone.now()
            config.validation_status = 'failed'
            config.validation_message = result.message
            config.save()
            return result

        cap_enum = (
            ProviderCapability.TEXT_GENERATION if config.capability == 'text'
            else ProviderCapability.IMAGE_GENERATION
        )

        validation = adapter.validate_credential(
            credential=credential_value,
            endpoint=config.endpoint_url,
            model_name=config.model_name,
            capability=cap_enum
        )

        config.last_validated = timezone.now()
        config.validation_status = 'success' if validation.success else 'failed'
        config.validation_message = validation.message
        config.save()

        if validation.success:
            credential_obj.last_used = timezone.now()
            credential_obj.save()

        return validation

    @staticmethod
    def get_active_provider_for_user(
        user,
        capability: str = 'text'
    ) -> Tuple[Optional[BaseProviderAdapter], Optional[str], Optional[str], Optional[str]]:
        """
        Resolve the active provider, credential, model, and endpoint for a user.

        First checks user-specific database configuration;
        falls back to canonical environment settings if no user config exists.

        Returns:
            Tuple of (adapter, credential, model_name, endpoint) or (None, None, None, None)
        """
        config = ProviderConfig.objects.filter(
            user=user,
            capability=capability,
            is_active=True
        ).first()

        if config:
            adapter = registry.get_provider(config.provider_name)
            cred_obj = config.get_active_credential()
            if adapter and cred_obj:
                cred_val = cred_obj.get_credential()
                if cred_val:
                    return adapter, cred_val, config.model_name or adapter.default_model, config.endpoint_url

        # Environment fallback for text generation
        if capability == 'text':
            env_provider = registry.get_environment_text_provider()
            if env_provider:
                adapter, api_key, model_name, endpoint = env_provider
                return adapter, api_key, model_name, endpoint

        # Environment fallback for image generation
        if capability == 'image':
            env_provider = registry.get_environment_image_provider()
            if env_provider:
                adapter, api_key, model_name, endpoint = env_provider
                return adapter, api_key, model_name, endpoint

        return None, None, None, None
