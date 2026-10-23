"""
Social publishing provider registry.

Centralized registry for all platform providers with factory methods.
"""
from typing import Dict, Optional, Type

from .base_provider import BaseSocialProvider
from .buffer_provider import BufferProvider
from .facebook_provider import FacebookProvider
from .linkedin_provider import LinkedInProvider
from .twitter_provider import TwitterProvider


class ProviderRegistry:
    """Registry of all available social publishing providers."""
    
    _providers: Dict[str, Type[BaseSocialProvider]] = {
        'buffer': BufferProvider,
        'linkedin': LinkedInProvider,
        'facebook': FacebookProvider,
        'twitter': TwitterProvider,
    }
    
    @classmethod
    def get_provider_class(cls, platform_key: str) -> Optional[Type[BaseSocialProvider]]:
        """Get provider class by platform key."""
        return cls._providers.get(platform_key)
    
    @classmethod
    def create_provider(cls, platform_key: str, **kwargs) -> Optional[BaseSocialProvider]:
        """
        Create provider instance by platform key.
        
        Args:
            platform_key: Platform identifier (buffer, linkedin, facebook, twitter)
            **kwargs: Provider-specific initialization parameters (access_token, etc.)
            
        Returns:
            Initialized provider instance or None if platform not found
        """
        provider_class = cls.get_provider_class(platform_key)
        if not provider_class:
            return None
        return provider_class(**kwargs)
    
    @classmethod
    def get_available_platforms(cls) -> list[str]:
        """Get list of all registered platform keys."""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, platform_key: str, provider_class: Type[BaseSocialProvider]):
        """Register a new provider (for extensibility)."""
        cls._providers[platform_key] = provider_class
