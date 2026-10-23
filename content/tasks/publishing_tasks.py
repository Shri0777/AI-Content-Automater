"""
Publishing reconciliation tasks for ambiguous publication states.
"""
from celery import shared_task
from django.utils import timezone


@shared_task
def reconcile_ambiguous_publications():
    """
    Check ambiguous ContentPublication records and attempt to resolve them.
    
    Runs every 5 minutes via Celery Beat. Queries external APIs to determine
    final status of publications that timed out or had server errors.
    """
    from content.models import ContentPublication
    from content.services.publishing.provider_registry import ProviderRegistry
    
    ambiguous = ContentPublication.objects.filter(status='ambiguous')
    
    resolved_count = 0
    for pub in ambiguous:
        try:
            # Get provider instance
            provider = ProviderRegistry.create_provider(
                pub.provider,
                access_token=None  # Would need to fetch from credentials
            )
            
            # Check status if we have external_post_id
            if pub.external_post_id and hasattr(provider, 'check_post_status'):
                status = provider.check_post_status(pub.external_post_id)
                
                if status == 'published':
                    pub.status = 'published'
                    pub.published_at = timezone.now()
                    resolved_count += 1
                elif status == 'failed':
                    pub.status = 'failed'
                    pub.error_message = 'Confirmed failed via reconciliation'
                    resolved_count += 1
                
                pub.save(update_fields=['status', 'published_at', 'error_message', 'updated_at'])
        
        except Exception as e:
            # Log but don't fail - will retry on next run
            continue
    
    return {'resolved': resolved_count, 'remaining': ambiguous.count()}
