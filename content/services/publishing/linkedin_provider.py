"""
LinkedIn direct publishing provider.

Implements OAuth2 authorization and LinkedIn API v2 posting.
Supports text posts and image sharing on personal profiles and company pages.

OAuth2 Scopes Required:
- w_member_social (post to personal profile)
- r_liteprofile (get user info)
- r_emailaddress (get email)

API Documentation: https://docs.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/share-api
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from .base_provider import (
    BaseSocialProvider,
    PublishingCapabilities,
    PublishingResult,
)

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.linkedin.com/v2"
OAUTH_URL = "https://www.linkedin.com/oauth/v2"


class LinkedInProvider(BaseSocialProvider):
    """
    LinkedIn direct publishing provider using OAuth2 and LinkedIn API v2.
    """
    
    provider_name = "linkedin"
    platform_key = "linkedin"
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 10,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        super().__init__(access_token, api_url or DEFAULT_API_URL, timeout)
        self.client_id = client_id or getattr(settings, 'LINKEDIN_CLIENT_ID', '')
        self.client_secret = client_secret or getattr(settings, 'LINKEDIN_CLIENT_SECRET', '')
    
    def get_capabilities(self) -> PublishingCapabilities:
        """LinkedIn supports text, images, and immediate publishing only."""
        return PublishingCapabilities(
            supports_text=True,
            supports_images=True,
            supports_video=False,
            supports_scheduling=False,  # LinkedIn API doesn't support scheduled posts
            max_text_length=3000,
            max_images=9,
            requires_oauth=True
        )
    
    def is_configured(self) -> bool:
        """Check if LinkedIn access token is configured."""
        if not self.access_token:
            return False
        token = self.access_token.strip()
        if not token or token.startswith('<'):
            return False
        # Basic validation - LinkedIn tokens are typically long alphanumeric strings
        return len(token) > 20
    
    def get_masked_token(self) -> Optional[str]:
        """Return masked LinkedIn token."""
        if not self.is_configured():
            return None
        return self.mask_token(self.access_token)
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Test LinkedIn connection via userinfo endpoint."""
        if not self.is_configured():
            return {
                'configured': False,
                'connected': False,
                'status': 'unconfigured',
                'error': 'LinkedIn access token not configured'
            }
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Call LinkedIn userinfo endpoint
            response = requests.get(
                f"{self.api_url}/me",
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'configured': True,
                    'connected': True,
                    'status': 'connected',
                    'user_id': data.get('id'),
                    'user_name': f"{data.get('localizedFirstName', '')} {data.get('localizedLastName', '')}".strip(),
                    'masked_token': self.get_masked_token()
                }
            elif response.status_code == 401:
                return {
                    'configured': True,
                    'connected': False,
                    'status': 'unauthorized',
                    'error': 'LinkedIn credentials invalid or expired',
                    'masked_token': self.get_masked_token()
                }
            else:
                return {
                    'configured': True,
                    'connected': False,
                    'status': 'error',
                    'error': f'LinkedIn API returned HTTP {response.status_code}',
                    'masked_token': self.get_masked_token()
                }
                
        except requests.exceptions.Timeout:
            return {
                'configured': True,
                'connected': False,
                'status': 'error',
                'error': 'LinkedIn API connection timed out'
            }
        except Exception as e:
            logger.error(f"LinkedIn connection test failed: {type(e).__name__}")
            return {
                'configured': True,
                'connected': False,
                'status': 'error',
                'error': f'Connection failure: {type(e).__name__}'
            }
    
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Generate LinkedIn OAuth2 authorization URL."""
        if not self.client_id:
            raise ValueError("LinkedIn client_id not configured")
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'scope': 'r_liteprofile r_emailaddress w_member_social'
        }
        
        return f"{OAUTH_URL}/authorization?{urlencode(params)}"
    
    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange LinkedIn OAuth2 authorization code for access token."""
        if not self.client_id or not self.client_secret:
            return {
                'success': False,
                'error': 'LinkedIn OAuth credentials not configured',
                'error_type': 'configuration_error'
            }
        
        try:
            response = requests.post(
                f"{OAUTH_URL}/accessToken",
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'access_token': data.get('access_token'),
                    'expires_in': data.get('expires_in'),
                    'refresh_token': data.get('refresh_token'),  # LinkedIn may not provide this
                }
            else:
                error_data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': error_data.get('error_description', f'HTTP {response.status_code}'),
                    'error_type': error_data.get('error', 'oauth_error')
                }
                
        except Exception as e:
            logger.error(f"LinkedIn code exchange failed: {e}")
            return {
                'success': False,
                'error': f'Code exchange failed: {type(e).__name__}',
                'error_type': 'exchange_error'
            }
    
    def validate_credentials(self) -> Dict[str, Any]:
        """Validate LinkedIn credentials and get user profile."""
        status = self.get_connection_status()
        return {
            'valid': status.get('connected', False),
            'user_id': status.get('user_id'),
            'user_name': status.get('user_name'),
            'error': status.get('error')
        }
    
    def publish_post(
        self,
        text: str,
        images: Optional[List[str]] = None,
        schedule_time: Optional[datetime] = None,
        person_urn: Optional[str] = None,
        **kwargs
    ) -> PublishingResult:
        """
        Publish post to LinkedIn.
        
        Args:
            text: Post text content (max 3000 chars)
            images: Optional image URLs (not yet implemented - requires LinkedIn UGC API)
            schedule_time: Not supported by LinkedIn API (immediate only)
            person_urn: LinkedIn person URN (e.g., 'urn:li:person:ABC123')
            **kwargs: Additional LinkedIn-specific parameters
        """
        if not self.is_configured():
            return PublishingResult(
                success=False,
                error='LinkedIn access token not configured',
                error_type='unconfigured'
            )
        
        if not text or not text.strip():
            return PublishingResult(
                success=False,
                error='Post text cannot be empty',
                error_type='empty_text'
            )
        
        if schedule_time is not None:
            return PublishingResult(
                success=False,
                error='LinkedIn API does not support scheduled publishing',
                error_type='not_supported'
            )
        
        # Get person URN if not provided
        if not person_urn:
            try:
                headers = {
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                }
                response = requests.get(
                    f"{self.api_url}/me",
                    headers=headers,
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    user_id = response.json().get('id')
                    person_urn = f"urn:li:person:{user_id}"
                else:
                    return PublishingResult(
                        success=False,
                        error='Failed to get LinkedIn user profile',
                        error_type='profile_error'
                    )
            except Exception as e:
                logger.error(f"LinkedIn profile lookup failed: {e}")
                return PublishingResult(
                    success=False,
                    error='Failed to retrieve user profile',
                    error_type='profile_error'
                )
        
        # Create LinkedIn share (UGC Post)
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0'
            }
            
            payload = {
                'author': person_urn,
                'lifecycleState': 'PUBLISHED',
                'specificContent': {
                    'com.linkedin.ugc.ShareContent': {
                        'shareCommentary': {
                            'text': text[:3000]  # Enforce max length
                        },
                        'shareMediaCategory': 'NONE'
                    }
                },
                'visibility': {
                    'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
                }
            }
            
            response = requests.post(
                f"{self.api_url}/ugcPosts",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                post_id = data.get('id', '')
                
                return PublishingResult(
                    success=True,
                    platform_post_id=post_id,
                    published_at=timezone.now(),
                    response_data={'post_urn': post_id}
                )
            elif response.status_code == 401:
                return PublishingResult(
                    success=False,
                    error='LinkedIn credentials invalid or expired',
                    error_type='unauthorized'
                )
            elif response.status_code == 429:
                return PublishingResult(
                    success=False,
                    error='LinkedIn rate limit exceeded',
                    error_type='rate_limited'
                )
            else:
                error_data = response.json() if response.content else {}
                return PublishingResult(
                    success=False,
                    error=f"LinkedIn API error: {error_data.get('message', response.status_code)}",
                    error_type='api_error'
                )
                
        except requests.exceptions.Timeout:
            return PublishingResult(
                success=False,
                error='LinkedIn post submission timed out',
                error_type='ambiguous_timeout',
                is_ambiguous=True
            )
        except Exception as e:
            logger.error(f"LinkedIn publish failed: {e}")
            return PublishingResult(
                success=False,
                error=f'Publish failed: {type(e).__name__}',
                error_type='publish_error'
            )
    
    def get_post_status(self, platform_post_id: str) -> Dict[str, Any]:
        """
        Check LinkedIn post status.
        
        Args:
            platform_post_id: LinkedIn post URN
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'LinkedIn not configured',
                'error_type': 'unconfigured'
            }
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.api_url}/ugcPosts/{platform_post_id}",
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'status': 'published',
                    'published': True,
                    'lifecycle_state': data.get('lifecycleState')
                }
            else:
                return {
                    'success': False,
                    'error': f'LinkedIn returned HTTP {response.status_code}',
                    'error_type': 'api_error'
                }
                
        except Exception as e:
            logger.error(f"LinkedIn post status check failed: {e}")
            return {
                'success': False,
                'error': f'Status check failed: {type(e).__name__}',
                'error_type': 'status_error'
            }
