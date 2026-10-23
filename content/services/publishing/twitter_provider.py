"""
Twitter/X publishing provider using API v2.

Supports OAuth 2.0 user context and tweet creation via Twitter API v2.
Requires elevated access and tweet.read + tweet.write + users.read scopes.

API Documentation: https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets
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

DEFAULT_API_URL = "https://api.twitter.com/2"
OAUTH_URL = "https://twitter.com/i/oauth2/authorize"


class TwitterProvider(BaseSocialProvider):
    """Twitter/X publishing provider using API v2."""
    
    provider_name = "twitter"
    platform_key = "twitter"
    
    def __init__(self, access_token: Optional[str] = None, api_url: Optional[str] = None, timeout: int = 10,
                 client_id: Optional[str] = None, client_secret: Optional[str] = None):
        super().__init__(access_token, api_url or DEFAULT_API_URL, timeout)
        self.client_id = client_id or getattr(settings, 'TWITTER_CLIENT_ID', '')
        self.client_secret = client_secret or getattr(settings, 'TWITTER_CLIENT_SECRET', '')
    
    def get_capabilities(self) -> PublishingCapabilities:
        return PublishingCapabilities(
            supports_text=True, supports_images=True, supports_video=False,
            supports_scheduling=False, max_text_length=280, max_images=4, requires_oauth=True
        )
    
    def is_configured(self) -> bool:
        return bool(self.access_token and len(self.access_token.strip()) > 20)
    
    def get_masked_token(self) -> Optional[str]:
        return self.mask_token(self.access_token) if self.is_configured() else None
    
    def get_connection_status(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {'configured': False, 'connected': False, 'status': 'unconfigured', 'error': 'Access token not configured'}
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            response = requests.get(f"{self.api_url}/users/me", headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json().get('data', {})
                return {'configured': True, 'connected': True, 'status': 'connected', 'user_id': data.get('id'), 'user_name': data.get('username')}
            elif response.status_code == 401:
                return {'configured': True, 'connected': False, 'status': 'unauthorized', 'error': 'Invalid or expired token'}
            else:
                return {'configured': True, 'connected': False, 'status': 'error', 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'configured': True, 'connected': False, 'status': 'error', 'error': str(type(e).__name__)}
    
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        params = {'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': redirect_uri, 'state': state,
                  'scope': 'tweet.read tweet.write users.read', 'code_challenge': 'challenge', 'code_challenge_method': 'plain'}
        return f"{OAUTH_URL}?{urlencode(params)}"
    
    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        try:
            response = requests.post("https://api.twitter.com/2/oauth2/token", data={
                'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri,
                'client_id': self.client_id, 'code_verifier': 'challenge'
            }, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return {'success': True, 'access_token': data.get('access_token'), 'refresh_token': data.get('refresh_token'), 'expires_in': data.get('expires_in')}
            return {'success': False, 'error': f'HTTP {response.status_code}', 'error_type': 'oauth_error'}
        except Exception as e:
            return {'success': False, 'error': str(type(e).__name__), 'error_type': 'exchange_error'}
    
    def validate_credentials(self) -> Dict[str, Any]:
        status = self.get_connection_status()
        return {'valid': status.get('connected', False), 'user_id': status.get('user_id'), 'user_name': status.get('user_name'), 'error': status.get('error')}
    
    def publish_post(self, text: str, images: Optional[List[str]] = None, schedule_time: Optional[datetime] = None, **kwargs) -> PublishingResult:
        if not self.is_configured():
            return PublishingResult(success=False, error='Twitter not configured', error_type='unconfigured')
        if not text.strip():
            return PublishingResult(success=False, error='Text cannot be empty', error_type='empty_text')
        if schedule_time:
            return PublishingResult(success=False, error='Twitter API does not support scheduled tweets', error_type='not_supported')
        
        try:
            headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
            payload = {'text': text[:280]}  # Enforce character limit
            
            response = requests.post(f"{self.api_url}/tweets", headers=headers, json=payload, timeout=self.timeout)
            if response.status_code == 201:
                data = response.json().get('data', {})
                return PublishingResult(success=True, platform_post_id=data.get('id'), published_at=timezone.now())
            elif response.status_code == 401:
                return PublishingResult(success=False, error='Token expired', error_type='unauthorized')
            elif response.status_code == 429:
                return PublishingResult(success=False, error='Rate limit exceeded', error_type='rate_limited')
            else:
                return PublishingResult(success=False, error=f'HTTP {response.status_code}', error_type='api_error')
        except requests.exceptions.Timeout:
            return PublishingResult(success=False, error='Timeout', error_type='ambiguous_timeout', is_ambiguous=True)
        except Exception as e:
            return PublishingResult(success=False, error=str(type(e).__name__), error_type='publish_error')
    
    def get_post_status(self, platform_post_id: str) -> Dict[str, Any]:
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            response = requests.get(f"{self.api_url}/tweets/{platform_post_id}", headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return {'success': True, 'status': 'published', 'published': True}
            return {'success': False, 'error': f'HTTP {response.status_code}', 'error_type': 'api_error'}
        except Exception as e:
            return {'success': False, 'error': str(type(e).__name__), 'error_type': 'status_error'}
