"""
Facebook/Meta publishing provider using Graph API.

Supports posting to Facebook Pages via OAuth2 and Graph API v18.0+.
Requires page access tokens with pages_manage_posts and pages_read_engagement permissions.

API Documentation: https://developers.facebook.com/docs/pages/publishing
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from .base_provider import BaseSocialProvider, PublishingCapabilities, PublishingResult

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://graph.facebook.com/v18.0"
OAUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"


class FacebookProvider(BaseSocialProvider):
    """Facebook/Meta publishing provider for Pages."""
    
    provider_name = "facebook"
    platform_key = "facebook"
    
    def __init__(self, access_token: Optional[str] = None, api_url: Optional[str] = None, timeout: int = 10,
                 client_id: Optional[str] = None, client_secret: Optional[str] = None, page_id: Optional[str] = None):
        super().__init__(access_token, api_url or DEFAULT_API_URL, timeout)
        self.client_id = client_id or getattr(settings, 'FACEBOOK_APP_ID', '')
        self.client_secret = client_secret or getattr(settings, 'FACEBOOK_APP_SECRET', '')
        self.page_id = page_id or getattr(settings, 'FACEBOOK_PAGE_ID', '')
    
    def get_capabilities(self) -> PublishingCapabilities:
        return PublishingCapabilities(
            supports_text=True, supports_images=True, supports_video=False,
            supports_scheduling=True, max_text_length=63206, max_images=10, requires_oauth=True
        )
    
    def is_configured(self) -> bool:
        return bool(self.access_token and len(self.access_token.strip()) > 20 and self.page_id)
    
    def get_masked_token(self) -> Optional[str]:
        return self.mask_token(self.access_token) if self.is_configured() else None
    
    def get_connection_status(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {'configured': False, 'connected': False, 'status': 'unconfigured', 'error': 'Access token or page ID not configured'}
        try:
            response = requests.get(f"{self.api_url}/me", params={'access_token': self.access_token}, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return {'configured': True, 'connected': True, 'status': 'connected', 'user_id': data.get('id'), 'user_name': data.get('name')}
            elif response.status_code == 190:  # Invalid token
                return {'configured': True, 'connected': False, 'status': 'unauthorized', 'error': 'Invalid or expired token'}
            else:
                return {'configured': True, 'connected': False, 'status': 'error', 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'configured': True, 'connected': False, 'status': 'error', 'error': str(type(e).__name__)}
    
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        params = {'client_id': self.client_id, 'redirect_uri': redirect_uri, 'state': state, 'scope': 'pages_manage_posts,pages_read_engagement'}
        return f"{OAUTH_URL}?{urlencode(params)}"
    
    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        try:
            response = requests.get(f"{self.api_url}/oauth/access_token", params={
                'client_id': self.client_id, 'client_secret': self.client_secret, 'redirect_uri': redirect_uri, 'code': code
            }, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return {'success': True, 'access_token': data.get('access_token'), 'expires_in': data.get('expires_in')}
            return {'success': False, 'error': f'HTTP {response.status_code}', 'error_type': 'oauth_error'}
        except Exception as e:
            return {'success': False, 'error': str(type(e).__name__), 'error_type': 'exchange_error'}
    
    def validate_credentials(self) -> Dict[str, Any]:
        status = self.get_connection_status()
        return {'valid': status.get('connected', False), 'user_id': status.get('user_id'), 'user_name': status.get('user_name'), 'error': status.get('error')}
    
    def publish_post(self, text: str, images: Optional[List[str]] = None, schedule_time: Optional[datetime] = None, **kwargs) -> PublishingResult:
        if not self.is_configured():
            return PublishingResult(success=False, error='Facebook not configured', error_type='unconfigured')
        if not text.strip():
            return PublishingResult(success=False, error='Text cannot be empty', error_type='empty_text')
        
        try:
            payload = {'message': text, 'access_token': self.access_token}
            if schedule_time and schedule_time > timezone.now():
                payload['published'] = 'false'
                payload['scheduled_publish_time'] = int(schedule_time.timestamp())
            
            response = requests.post(f"{self.api_url}/{self.page_id}/feed", data=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return PublishingResult(success=True, platform_post_id=data.get('id'), published_at=timezone.now() if not schedule_time else None)
            elif response.status_code == 190:
                return PublishingResult(success=False, error='Token expired', error_type='unauthorized')
            else:
                return PublishingResult(success=False, error=f'HTTP {response.status_code}', error_type='api_error')
        except requests.exceptions.Timeout:
            return PublishingResult(success=False, error='Timeout', error_type='ambiguous_timeout', is_ambiguous=True)
        except Exception as e:
            return PublishingResult(success=False, error=str(type(e).__name__), error_type='publish_error')
    
    def get_post_status(self, platform_post_id: str) -> Dict[str, Any]:
        try:
            response = requests.get(f"{self.api_url}/{platform_post_id}", params={'access_token': self.access_token, 'fields': 'id,is_published'}, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return {'success': True, 'status': 'published' if data.get('is_published') else 'draft', 'published': data.get('is_published', False)}
            return {'success': False, 'error': f'HTTP {response.status_code}', 'error_type': 'api_error'}
        except Exception as e:
            return {'success': False, 'error': str(type(e).__name__), 'error_type': 'status_error'}
