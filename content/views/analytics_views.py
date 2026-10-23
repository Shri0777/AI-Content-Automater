"""
Analytics and reporting views (FR-011).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from datetime import timedelta
from django.utils import timezone

from content.services.analytics_service import AnalyticsService


@login_required
def analytics_dashboard(request):
    """Show analytics dashboard with key metrics."""
    # Get time range from request (default 30 days)
    days = int(request.GET.get('days', 30))
    if days not in [7, 30, 90]:
        days = 30
    
    # Get all analytics
    publishing_summary = AnalyticsService.get_user_publishing_summary(
        user=request.user,
        days=days
    )
    
    campaign_analytics = AnalyticsService.get_campaign_analytics(
        user=request.user
    )
    
    content_analytics = AnalyticsService.get_content_analytics(
        user=request.user,
        days=days
    )
    
    dashboard_summary = AnalyticsService.get_dashboard_summary(
        user=request.user
    )
    
    context = {
        'days': days,
        'publishing': publishing_summary,
        'campaigns': campaign_analytics,
        'content': content_analytics,
        'summary': dashboard_summary,
        'page_title': 'Analytics Dashboard'
    }
    return render(request, 'content/analytics/dashboard.html', context)


@login_required
def analytics_publishing(request):
    """Detailed publishing analytics."""
    days = int(request.GET.get('days', 30))
    if days not in [7, 30, 90]:
        days = 30
    
    publishing_summary = AnalyticsService.get_user_publishing_summary(
        user=request.user,
        days=days
    )
    
    context = {
        'days': days,
        'publishing': publishing_summary,
        'page_title': 'Publishing Analytics'
    }
    return render(request, 'content/analytics/publishing.html', context)


@login_required
def analytics_campaigns(request):
    """Detailed campaign analytics."""
    campaign_analytics = AnalyticsService.get_campaign_analytics(
        user=request.user
    )
    
    context = {
        'campaigns': campaign_analytics,
        'page_title': 'Campaign Analytics'
    }
    return render(request, 'content/analytics/campaigns.html', context)
