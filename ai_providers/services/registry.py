"""
Provider registry for managing available AI provider adapters.

Tracks registered provider adapters, supports evidence-based provider discovery,
and provides standardized access to AI capabilities.
"""
import logging
from typing import Dict, List, Optional

from django.conf import settings

from .base_adapter import BaseProviderAdapter, ProviderCapability
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .nvidia_adapter import NVIDIAAdapter
from .nvidia_flux_adapter import NVIDIAFluxAdapter

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry of all available AI provider adapters.

    Singleton pattern - access via ProviderRegistry.get_instance() or `registry`.
    """

    _instance: Optional['ProviderRegistry'] = None

    def __init__(self):
        self._providers: Dict[str, BaseProviderAdapter] = {}
        self.register_defaults()

    @classmethod
    def get_instance(cls) -> 'ProviderRegistry':
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, adapter: BaseProviderAdapter) -> None:
        """
        Register a provider adapter instance.
        """
        self._providers[adapter.provider_name.lower()] = adapter

    def register_defaults(self) -> None:
        """Register built-in default provider adapters."""
        self.register(OpenAIAdapter())
        self.register(AnthropicAdapter())
        self.register(NVIDIAAdapter())
        self.register(NVIDIAFluxAdapter())

    def get_provider(self, provider_name: str) -> Optional[BaseProviderAdapter]:
        """
        Get a registered provider adapter by identifier.
        """
        if not provider_name:
            return None
        return self._providers.get(provider_name.strip().lower())

    def get_all_providers(self) -> List[BaseProviderAdapter]:
        """Get a list of all registered provider adapters."""
        return list(self._providers.values())

    def get_providers_by_capability(
        self,
        capability: ProviderCapability | str
    ) -> List[BaseProviderAdapter]:
        """
        Get all providers supporting a specific capability.
        """
        if isinstance(capability, str):
            normalized = capability.strip().lower()
            if normalized not in {'text', 'image'}:
                return []
            cap_enum = ProviderCapability.TEXT_GENERATION if normalized == 'text' else ProviderCapability.IMAGE_GENERATION
        else:
            cap_enum = capability

        return [
            p for p in self._providers.values()
            if cap_enum in p.supported_capabilities
        ]

    def identify_provider(
        self,
        credential: str,
        endpoint: Optional[str] = None
    ) -> Optional[BaseProviderAdapter]:
        """
        Attempt to identify which provider a credential belongs to.

        Uses evidence-based probing rather than solely key prefix inspection.
        Returns the identified provider adapter, or None if inconclusive.
        """
        if not credential or not credential.strip():
            return None

        identified = []
        for provider in self._providers.values():
            try:
                if provider.identify_provider(credential, endpoint=endpoint):
                    identified.append(provider)
            except Exception as e:
                logger.debug(f"Provider identification failed for {provider.provider_name}: {e}")
                continue

        # Return provider only if uniquely identified without ambiguity
        if len(identified) == 1:
            return identified[0]

        return None

    def get_environment_text_provider(self) -> Optional[tuple[BaseProviderAdapter, str, Optional[str], Optional[str]]]:
        """
        Check if a valid canonical environment provider is configured via settings.

        Returns:
            Tuple of (adapter, api_key, model_name, endpoint) or None
        """
        api_key = getattr(settings, 'TEXT_API_KEY', '').strip()
        if not api_key:
            return None

        provider_name = getattr(settings, 'TEXT_PROVIDER', 'auto').strip().lower()
        model_name = getattr(settings, 'TEXT_MODEL', '').strip() or None
        endpoint = getattr(settings, 'TEXT_API_BASE_URL', '').strip() or None

        if provider_name and provider_name != 'auto':
            adapter = self.get_provider(provider_name)
            if adapter:
                return adapter, api_key, model_name or adapter.default_model, endpoint

        # Auto-identification
        adapter = self.identify_provider(api_key, endpoint=endpoint)
        if adapter:
            return adapter, api_key, model_name or adapter.default_model, endpoint

        # Never guess a provider for an ambiguous credential. The caller must
        # configure TEXT_PROVIDER explicitly or select a provider in the dashboard.
        logger.warning('TEXT_API_KEY is configured but TEXT_PROVIDER could not be identified; no provider selected.')
        return None

    def get_environment_image_provider(self) -> Optional[tuple[BaseProviderAdapter, str, Optional[str], Optional[str]]]:
        """
        Check if a valid canonical environment image provider is configured via settings.

        Returns:
            Tuple of (adapter, api_key, model_name, endpoint) or None
        """
        api_key = getattr(settings, 'IMAGE_API_KEY', '').strip()
        if not api_key:
            return None

        provider_name = getattr(settings, 'IMAGE_PROVIDER', 'auto').strip().lower()
        model_name = getattr(settings, 'IMAGE_MODEL', '').strip() or None

        if provider_name and provider_name != 'auto':
            adapter = self.get_provider(provider_name)
            if adapter:
                return adapter, api_key, model_name or adapter.default_model, None

        # Auto-identification for image providers
        adapter = self.identify_provider(api_key)
        if adapter and ProviderCapability.IMAGE_GENERATION in adapter.supported_capabilities:
            return adapter, api_key, model_name or adapter.default_model, None

        logger.warning('IMAGE_API_KEY is configured but IMAGE_PROVIDER could not be identified; no provider selected.')
        return None

    def clear(self) -> None:
        """Clear all registered adapters (primarily for testing)."""
        self._providers.clear()


# Global singleton instance
registry = ProviderRegistry.get_instance()
