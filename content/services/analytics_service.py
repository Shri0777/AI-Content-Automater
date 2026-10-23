"""
Analytics Service for content and publishing metrics (FR-011).

Provides basic analytics based on actual database records.
Does not invent platform engagement metrics when APIs don't provide them.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Count, Q
from django.utils import timezone

from content.models import (
    Content,
    ContentPublication,
    PublicationMetrics,
    Campaign,
    CampaignExecution,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for generating analytics and metrics reports.
    """
    
    @staticmethod
    def get_user_publishing_summary(user: Any, days: int = 30) -> Dict[str, Any]:
        """
        Get publishing summary for a user over specified time period.
        
        Args:
            user: User object
            days: Number of days to look back
            
        Returns:
            Dict with publishing metrics
        """
        since = timezone.now() - timedelta(days=days)
        
        # Get user's content
        content_ids = Content.objects.filter(owner=user).values_list('id', flat=True)
        
        # Publication stats
        publications = ContentPublication.objects.filter(
            content_id__in=content_ids,
            created_at__gte=since
        )
        
        total_publications = publications.count()
        successful = publications.filter(status='published').count()
        failed = publications.filter(status='failed').count()
        scheduled = publications.filter(status='scheduled').count()
        pending = publications.filter(status='pending').count()
        
        # Platform breakdown
        platform_stats = publications.values('provider').annotate(
            total=Count('id')
        ).order_by('-total')
        
        return {
            'period_days': days,
            'since': since,
            'total_publications': total_publications,
            'successful': successful,
            'failed': failed,
            'scheduled': scheduled,
            'pending': pending,
            'success_rate': (successful / total_publications * 100) if total_publications > 0 else 0,
            'platform_breakdown': list(platform_stats),
        }
    
    @staticmethod
    def get_campaign_analytics(user: Any, campaign_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get campaign execution analytics.
        
        Args:
            user: User object
            campaign_id: Optional specific campaign ID
            
        Returns:
            Dict with campaign metrics
        """
        campaigns_qs = Campaign.objects.filter(owner=user)
        
        if campaign_id:
            campaigns_qs = campaigns_qs.filter(id=campaign_id)
        
        campaigns = campaigns_qs.all()
        
        if not campaigns:
            return {
                'total_campaigns': 0,
                'active_campaigns': 0,
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
            }
        
        total_campaigns = campaigns.count()
        active_campaigns = campaigns.filter(status='active').count()
        
        # Execution stats
        execution_ids = []
        total_executions = 0
        successful_executions = 0
        failed_executions = 0
        
        for campaign in campaigns:
            total_executions += campaign.execution_count
            successful_executions += campaign.success_count
            failed_executions += campaign.failure_count
        
        return {
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'success_rate': (successful_executions / total_executions * 100) if total_executions > 0 else 0,
        }
    
    @staticmethod
    def get_content_analytics(user: Any, days: int = 30) -> Dict[str, Any]:
        """
        Get content creation and lifecycle analytics.
        
        Args:
            user: User object
            days: Number of days to look back
            
        Returns:
            Dict with content metrics
        """
        since = timezone.now() - timedelta(days=days)
        
        content_qs = Content.objects.filter(owner=user, created_at__gte=since)
        
        total_content = content_qs.count()
        
        # Lifecycle breakdown
        lifecycle_stats = content_qs.values('lifecycle_state').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent content
        recent_content = content_qs.order_by('-created_at')[:10]
        
        return {
            'period_days': days,
            'since': since,
            'total_content': total_content,
            'lifecycle_breakdown': list(lifecycle_stats),
            'recent_content': [
                {
                    'id': c.id,
                    'title': c.title,
                    'state': c.lifecycle_state,
                    'created_at': c.created_at,
                }
                for c in recent_content
            ],
        }
    
    @staticmethod
    def get_platform_metrics(publication_id: int) -> Optional[PublicationMetrics]:
        """
        Get or create platform metrics for a publication.
        
        Note: This returns operational metrics. Platform engagement metrics
        (impressions, clicks) are only available if the platform API provides them.
        
        Args:
            publication_id: ContentPublication ID
            
        Returns:
            PublicationMetrics object or None
        """
        try:
            publication = ContentPublication.objects.get(id=publication_id)
            
            if publication.status != 'published':
                return None
            
            # Get or create metrics
            metrics, created = PublicationMetrics.objects.get_or_create(
                publication=publication,
                defaults={
                    'platform': publication.provider,
                    'published_at': publication.published_at or timezone.now(),
                    'collection_status': 'unavailable',  # Most platforms don't expose metrics
                }
            )
            
            return metrics
            
        except ContentPublication.DoesNotExist:
            return None
    
    @staticmethod
    def get_dashboard_summary(user: Any) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary for user.
        
        Args:
            user: User object
            
        Returns:
            Dict with all key metrics
        """
        return {
            'publishing': AnalyticsService.get_user_publishing_summary(user, days=30),
            'campaigns': AnalyticsService.get_campaign_analytics(user),
            'content': AnalyticsService.get_content_analytics(user, days=30),
        }
