"""
Base provider adapter interface and standard data structures.

Defines the contract all AI provider adapters must implement for
provider-agnostic text and optional image generation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderCapability(Enum):
    """Supported AI provider capabilities."""
    TEXT_GENERATION = "text"
    IMAGE_GENERATION = "image"


class AuthMethod(Enum):
    """Supported authentication methods."""
    API_KEY_HEADER = "api_key_header"
    BEARER_TOKEN = "bearer_token"


class ProviderErrorType:
    """Standardized error categories for provider operations."""
    MISSING_CREDENTIAL = "missing_credential"
    INVALID_CREDENTIAL = "invalid_credential"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    AMBIGUOUS_PROVIDER = "ambiguous_provider"
    MODEL_UNAVAILABLE = "model_unavailable"
    LACKS_CAPABILITY = "lacks_capability"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    MALFORMED_RESPONSE = "malformed_response"
    SSRF_BLOCKED = "ssrf_blocked"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of credential and capability validation."""
    success: bool
    message: str
    provider_identified: Optional[str] = None
    capabilities: Optional[List[str]] = None
    model_available: Optional[str] = None
    error_type: Optional[str] = None


@dataclass
class GenerationRequest:
    """Normalized request for AI content generation."""
    prompt: str
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    endpoint: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Normalized result of AI generation request."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    model_used: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None


class BaseProviderAdapter(ABC):
    """
    Base class for all AI provider adapters.
    
    Each adapter implements provider-specific authentication, validation,
    and generation logic while exposing a normalized interface.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'openai', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        pass
    
    @property
    @abstractmethod
    def supported_capabilities(self) -> List[ProviderCapability]:
        """List of capabilities this provider supports."""
        pass
    
    @property
    @abstractmethod
    def auth_method(self) -> AuthMethod:
        """Authentication method used by this provider."""
        pass
    
    @property
    @abstractmethod
    def default_endpoint(self) -> str:
        """Default API endpoint URL."""
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier."""
        pass
    
    @property
    @abstractmethod
    def requires_model_name(self) -> bool:
        """Whether this provider requires explicit model selection."""
        pass
    
    @abstractmethod
    def identify_provider(self, credential: str, endpoint: Optional[str] = None) -> bool:
        """
        Attempt to identify if a credential belongs to this provider.
        
        Uses evidence-based identification (e.g., API structure, models probe)
        NOT solely key prefix patterns.
        """
        pass
    
    @abstractmethod
    def validate_credential(
        self,
        credential: str,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        capability: Optional[ProviderCapability] = None
    ) -> ValidationResult:
        """
        Validate credential, endpoint safety, and capability/model availability.
        """
        pass
    
    @abstractmethod
    def generate_text(
        self,
        request: GenerationRequest | str,
        credential: str,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate text using this provider with bounded retries and error mapping.
        """
        pass
    
    def generate_image(
        self,
        prompt: str,
        credential: str,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate image using this provider.
        Default implementation returns unsupported error.
        """
        return GenerationResult(
            success=False,
            error=f"{self.display_name} does not support image generation in Phase 3",
            error_type=ProviderErrorType.LACKS_CAPABILITY
        )
    
    def get_available_models(
        self,
        credential: str,
        endpoint: Optional[str] = None,
        capability: Optional[ProviderCapability] = None
    ) -> List[str]:
        """
        Get list of available models for this provider.
        Default implementation returns empty list.
        """
        return []
