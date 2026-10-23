"""
Multi-platform publishing orchestrator.

Coordinates publishing to multiple social platforms with independent result tracking.
Implements FR-032 (direct platform publishing) and FR-034 (independent platform results).
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from content.models import Content, ContentPublication, WorkflowAuditLog

from .provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)
User = get_user_model()


class MultiPlatformPublishingOrchestrator:
    """
    Orchestrates content publishing across multiple social platforms.
    
    Each platform publishes independently - failures on one platform don't
    affect others. Results are tracked per-platform in ContentPublication records.
    """
    
    @staticmethod
    def publish_to_platforms(
        content_id: int,
        user: User,
        platforms: List[Dict[str, Any]],
        schedule_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Publish content to multiple platforms independently.
        
        Args:
            content_id: Content PK to publish
            user: Authenticated user (ownership verified)
            platforms: List of platform configurations, each with:
                - platform: Platform key (buffer, linkedin, facebook, twitter)
                - access_token: Platform access token
                - profile_ids: Optional list of destination IDs (for Buffer)
                - page_id: Optional page ID (for Facebook)
                - Additional platform-specific config
            schedule_time: Optional future publication time
            
        Returns:
            Dict with overall_success, platforms (per-platform results), and summary
        """
        content = Content.objects.filter(pk=content_id, owner=user).first()
        if not content:
            return {
                'success': False,
                'error': 'Content not found or unauthorized',
                'error_type': 'not_found'
            }
        
        current_version = content.current_version
        if not current_version:
            return {
                'success': False,
                'error': 'No current version available to publish',
                'error_type': 'no_version'
            }
        
        if not current_version.is_approved:
            return {
                'success': False,
                'error': 'Content must be approved before publishing',
                'error_type': 'not_approved'
            }
        
        if not platforms:
            return {
                'success': False,
                'error': 'At least one platform must be specified',
                'error_type': 'no_platforms'
            }
        
        text = current_version.content_text
        if not text or not text.strip():
            return {
                'success': False,
                'error': 'Content text cannot be empty',
                'error_type': 'empty_content'
            }
        
        # Publish to each platform independently
        platform_results = []
        successful_platforms = []
        failed_platforms = []
        
        for platform_config in platforms:
            platform_key = platform_config.get('platform')
            if not platform_key:
                platform_results.append({
                    'platform': 'unknown',
                    'success': False,
                    'error': 'Platform key not specified'
                })
                failed_platforms.append('unknown')
                continue
            
            result = MultiPlatformPublishingOrchestrator._publish_to_single_platform(
                content=content,
                content_version=current_version,
                user=user,
                platform_key=platform_key,
                platform_config=platform_config,
                text=text,
                schedule_time=schedule_time
            )
            
            platform_results.append(result)
            
            if result.get('success'):
                successful_platforms.append(platform_key)
            else:
                failed_platforms.append(platform_key)
        
        # Overall success if at least one platform succeeded
        overall_success = len(successful_platforms) > 0
        
        # Update content lifecycle if any publications succeeded
        if overall_success and content.lifecycle_state != 'published':
            try:
                content.transition_to('published')
            except Exception as e:
                logger.warning(f"Content lifecycle transition to published failed: {e}")
        
        # Audit log
        WorkflowAuditLog.objects.create(
            content=content,
            content_version=current_version,
            user=user,
            event_type='multi_platform_publish',
            from_state=content.lifecycle_state,
            to_state=content.lifecycle_state,
            message=f"Published to {len(successful_platforms)}/{len(platforms)} platforms",
            details={
                'successful': successful_platforms,
                'failed': failed_platforms,
                'scheduled': bool(schedule_time)
            }
        )
        
        return {
            'overall_success': overall_success,
            'platforms': platform_results,
            'summary': {
                'total': len(platforms),
                'successful': len(successful_platforms),
                'failed': len(failed_platforms),
                'successful_platforms': successful_platforms,
                'failed_platforms': failed_platforms
            }
        }
    
    @staticmethod
    def _publish_to_single_platform(
        content: Content,
        content_version: Any,
        user: User,
        platform_key: str,
        platform_config: Dict[str, Any],
        text: str,
        schedule_time: Optional[datetime]
    ) -> Dict[str, Any]:
        """
        Publish to a single platform and record result in ContentPublication.
        
        Returns:
            Dict with platform, success, publication_id, error details
        """
        try:
            # Create provider instance
            provider = ProviderRegistry.create_provider(
                platform_key=platform_key,
                access_token=platform_config.get('access_token'),
                api_url=platform_config.get('api_url'),
                timeout=platform_config.get('timeout', 10),
                # Platform-specific config
                client_id=platform_config.get('client_id'),
                client_secret=platform_config.get('client_secret'),
                page_id=platform_config.get('page_id')
            )
            
            if not provider:
                return {
                    'platform': platform_key,
                    'success': False,
                    'error': f'Unknown platform: {platform_key}',
                    'error_type': 'unknown_platform'
                }
            
            if not provider.is_configured():
                return {
                    'platform': platform_key,
                    'success': False,
                    'error': f'{platform_key} not configured or invalid credentials',
                    'error_type': 'not_configured'
                }
            
            # Create ContentPublication record (pending)
            publication = ContentPublication.objects.create(
                content=content,
                content_version=content_version,
                user=user,
                provider=platform_key,
                profile_id='direct',  # Direct platform publishing (not via Buffer profile)
                status='pending',
                scheduled_at=schedule_time,
                mode='scheduled' if schedule_time else 'immediate',
                payload_text=text,
                idempotency_key=f"{content.id}_{content_version.id}_{platform_key}_{timezone.now().timestamp()}"
            )
            
            # Publish via provider
            publish_kwargs = {
                'text': text,
                'schedule_time': schedule_time
            }
            
            # Add platform-specific parameters
            if platform_key == 'buffer':
                publish_kwargs['profile_ids'] = platform_config.get('profile_ids', [])
            elif platform_key == 'facebook':
                publish_kwargs['page_id'] = platform_config.get('page_id')
            
            publish_result = provider.publish_post(**publish_kwargs)
            
            # Update ContentPublication with result
            if publish_result.success:
                publication.status = 'published' if not schedule_time else 'scheduled'
                publication.external_post_id = publish_result.platform_post_id
                publication.published_at = publish_result.published_at or timezone.now()
                publication.response_data = publish_result.response_data
                publication.save()
                
                return {
                    'platform': platform_key,
                    'success': True,
                    'publication_id': publication.id,
                    'platform_post_id': publish_result.platform_post_id,
                    'published_at': publish_result.published_at
                }
            else:
                publication.status = 'ambiguous' if publish_result.is_ambiguous else 'failed'
                publication.error_message = publish_result.error
                publication.error_type = publish_result.error_type
                publication.response_data = publish_result.response_data
                publication.save()
                
                return {
                    'platform': platform_key,
                    'success': False,
                    'publication_id': publication.id,
                    'error': publish_result.error,
                    'error_type': publish_result.error_type,
                    'is_ambiguous': publish_result.is_ambiguous
                }
                
        except Exception as e:
            logger.error(f"Unexpected error publishing to {platform_key}: {e}")
            return {
                'platform': platform_key,
                'success': False,
                'error': f'Unexpected error: {type(e).__name__}',
                'error_type': 'unexpected_error'
            }
