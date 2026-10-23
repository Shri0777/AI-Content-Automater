"""
Base social media publishing provider abstraction.

Defines the standard interface all platform-specific providers must implement.
Supports OAuth2 flows, credential validation, and publishing operations.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class PublishingCapabilities:
    """Declaration of platform-specific features."""
    
    def __init__(
        self,
        supports_text: bool = True,
        supports_images: bool = False,
        supports_video: bool = False,
        supports_scheduling: bool = False,
        max_text_length: Optional[int] = None,
        max_images: int = 0,
        requires_oauth: bool = True
    ):
        self.supports_text = supports_text
        self.supports_images = supports_images
        self.supports_video = supports_video
        self.supports_scheduling = supports_scheduling
        self.max_text_length = max_text_length
        self.max_images = max_images
        self.requires_oauth = requires_oauth


class PublishingResult:
    """Standardized result from a publishing operation."""
    
    def __init__(
        self,
        success: bool,
        platform_post_id: Optional[str] = None,
        platform_url: Optional[str] = None,
        published_at: Optional[datetime] = None,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
        is_ambiguous: bool = False,
        response_data: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.platform_post_id = platform_post_id
        self.platform_url = platform_url
        self.published_at = published_at
        self.error = error
        self.error_type = error_type
        self.is_ambiguous = is_ambiguous
        self.response_data = response_data or {}


class BaseSocialProvider(ABC):
    """
    Abstract base class for all social media publishing providers.
    
    Each platform provider implements:
    - OAuth2 authorization flow
    - Credential validation
    - Publishing operations (immediate and scheduled)
    - Error handling and result normalization
    """
    
    provider_name: str = "unknown"
    platform_key: str = "unknown"  # matches ContentPublication.platform choices
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 10
    ):
        """
        Initialize provider with credentials.
        
        Args:
            access_token: OAuth2 access token (platform-specific format)
            api_url: Optional API endpoint override
            timeout: Request timeout in seconds
        """
        self.access_token = access_token
        self.api_url = api_url
        self.timeout = timeout
    
    @abstractmethod
    def get_capabilities(self) -> PublishingCapabilities:
        """Return platform feature capabilities."""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if provider has valid credentials configured."""
        pass
    
    @abstractmethod
    def get_masked_token(self) -> Optional[str]:
        """Return safely masked token for UI display, or None if unconfigured."""
        pass
    
    @abstractmethod
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Test connection and validate credentials.
        
        Returns:
            Dict with configured, connected, status, user info, and error details.
        """
        pass
    
    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate OAuth2 authorization URL.
        
        Args:
            redirect_uri: OAuth callback URL
            state: CSRF protection state parameter
            
        Returns:
            Authorization URL for user to visit
        """
        pass
    
    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange OAuth2 authorization code for access token.
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in get_auth_url
            
        Returns:
            Dict with success, access_token, refresh_token, expires_in, or error
        """
        pass
    
    @abstractmethod
    def validate_credentials(self) -> Dict[str, Any]:
        """
        Validate current access token and retrieve account info.
        
        Returns:
            Dict with valid flag, account metadata, or error details.
        """
        pass
    
    @abstractmethod
    def publish_post(
        self,
        text: str,
        images: Optional[List[str]] = None,
        schedule_time: Optional[datetime] = None,
        **kwargs
    ) -> PublishingResult:
        """
        Publish content to the platform.
        
        Args:
            text: Post text content
            images: Optional list of image URLs or file paths
            schedule_time: Optional future publication time
            **kwargs: Platform-specific parameters
            
        Returns:
            PublishingResult with success, post ID, URL, or error details
        """
        pass
    
    @abstractmethod
    def get_post_status(self, platform_post_id: str) -> Dict[str, Any]:
        """
        Check status of a published post.
        
        Args:
            platform_post_id: Platform-specific post identifier
            
        Returns:
            Dict with status, published, scheduled, error, and metadata
        """
        pass
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token (if platform supports it).
        
        Args:
            refresh_token: Platform refresh token
            
        Returns:
            Dict with success, new access_token, refresh_token, expires_in, or error
        """
        return {
            'success': False,
            'error': f"{self.provider_name} does not support token refresh",
            'error_type': 'not_supported'
        }
    
    @staticmethod
    def mask_token(token: Optional[str], prefix_chars: int = 4, suffix_chars: int = 4) -> str:
        """
        Safely mask an access token for display.
        
        Args:
            token: Token to mask
            prefix_chars: Number of prefix characters to show
            suffix_chars: Number of suffix characters to show
            
        Returns:
            Masked token string
        """
        if not token:
            return "Not configured"
        clean = token.strip()
        if len(clean) <= (prefix_chars + suffix_chars):
            return "Configured"
        return f"{clean[:prefix_chars]}...{clean[-suffix_chars:]}"
