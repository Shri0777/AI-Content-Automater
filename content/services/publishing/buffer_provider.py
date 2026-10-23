"""
Buffer publishing provider implementation.

Wraps the existing BufferPublishingService to conform to the BaseSocialProvider interface.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from content.services.buffer_service import BufferPublishingService

from .base_provider import (
    BaseSocialProvider,
    PublishingCapabilities,
    PublishingResult,
)

logger = logging.getLogger(__name__)


class BufferProvider(BaseSocialProvider):
    """
    Buffer publishing provider wrapping the GraphQL service.
    
    Buffer acts as a multi-platform publishing intermediary that can post to
    LinkedIn, Facebook, Twitter, Instagram, and other platforms through a
    unified API.
    """
    
    provider_name = "buffer"
    platform_key = "buffer"
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 10
    ):
        super().__init__(access_token, api_url, timeout)
        # Use sentinel pattern for proper test isolation
        from content.services.buffer_service import _UNSET
        if access_token is None:
            self.service = BufferPublishingService(access_token=_UNSET, api_url=api_url, timeout=timeout)
        else:
            self.service = BufferPublishingService(access_token=access_token, api_url=api_url, timeout=timeout)
    
    def get_capabilities(self) -> PublishingCapabilities:
        """Buffer supports text, images, and scheduling."""
        return PublishingCapabilities(
            supports_text=True,
            supports_images=True,
            supports_video=False,
            supports_scheduling=True,
            max_text_length=None,  # Varies by target platform
            max_images=10,
            requires_oauth=True
        )
    
    def is_configured(self) -> bool:
        """Check if Buffer access token is configured."""
        return self.service.is_configured()
    
    def get_masked_token(self) -> Optional[str]:
        """Return masked Buffer token."""
        return self.service.get_masked_token()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Test Buffer connection and validate credentials."""
        return self.service.get_connection_status()
    
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """
        Buffer uses manual token generation, not OAuth2 flow.
        
        Users must visit https://account.buffer.com/developers to generate tokens.
        """
        return f"https://account.buffer.com/developers?redirect_uri={redirect_uri}&state={state}"
    
    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Buffer doesn't support OAuth2 code exchange.
        
        Tokens are generated manually from the Buffer dashboard.
        """
        return {
            'success': False,
            'error': 'Buffer uses manual token generation. Visit https://account.buffer.com/developers',
            'error_type': 'not_supported'
        }
    
    def validate_credentials(self) -> Dict[str, Any]:
        """Validate Buffer credentials via account query."""
        status = self.service.get_connection_status()
        return {
            'valid': status.get('connected', False),
            'user_id': status.get('user_id'),
            'user_name': status.get('user_name'),
            'email': status.get('email'),
            'error': status.get('error')
        }
    
    def publish_post(
        self,
        text: str,
        images: Optional[List[str]] = None,
        schedule_time: Optional[datetime] = None,
        profile_ids: Optional[List[str]] = None,
        **kwargs
    ) -> PublishingResult:
        """
        Publish post to Buffer channels.
        
        Args:
            text: Post text content
            images: Optional image URLs/paths (not yet implemented in Buffer service)
            schedule_time: Optional future publication time
            profile_ids: Buffer channel IDs to publish to
            **kwargs: Additional Buffer-specific parameters
        """
        if not profile_ids:
            return PublishingResult(
                success=False,
                error='Buffer requires at least one profile_id (channel) to publish to',
                error_type='missing_destination'
            )
        
        # Convert to Buffer service parameters
        now = schedule_time is None
        due_at = schedule_time
        
        result = self.service.create_update(
            profile_ids=profile_ids,
            text=text,
            now=now,
            due_at=due_at
        )
        
        if result.get('success'):
            updates = result.get('updates', [])
            first_update = updates[0] if updates else {}
            
            return PublishingResult(
                success=True,
                platform_post_id=first_update.get('id'),
                published_at=datetime.now() if now else None,
                response_data=result.get('response_data', {})
            )
        else:
            return PublishingResult(
                success=False,
                error=result.get('error'),
                error_type=result.get('error_type'),
                is_ambiguous=result.get('is_ambiguous', False),
                response_data=result.get('response_data', {})
            )
    
    def get_post_status(self, platform_post_id: str) -> Dict[str, Any]:
        """
        Check Buffer post status.
        
        Note: Current Buffer service doesn't implement status checking.
        This is a placeholder for future implementation.
        """
        return {
            'success': False,
            'error': 'Buffer post status checking not yet implemented',
            'error_type': 'not_implemented'
        }
