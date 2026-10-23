"""
Campaign execution tasks for recurring content generation (FR-029, FR-030, FR-031).
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta


@shared_task(bind=True, max_retries=2)
def execute_campaign_task(self, campaign_id):
    """
    Execute complete campaign workflow: research → generate → review → correct → review.
    
    Creates content through the full AI workflow pipeline using existing services.
    Does NOT auto-approve - content ends in pending_review state for manual approval.
    
    Args:
        campaign_id: Campaign primary key
    
    Returns:
        dict: Execution result with status, content_id, and any errors
    """
    from content.models import Campaign, CampaignExecution, Content, ContentVersion
    from content.services.generation_service import GenerationService
    from content.services.review_service import ReviewService
    from content.services.correction_service import CorrectionService
    from research.models import ContentCreationRequest
    
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        return {'success': False, 'error': 'Campaign not found'}
    
    # Create execution record
    execution = CampaignExecution.objects.create(
        campaign=campaign,
        scheduled_time=timezone.now(),
        started_at=timezone.now(),
        status='researching'
    )
    
    try:
        # Step 1: Create Content object
        content = Content.objects.create(
            owner=campaign.owner,
            title=f"{campaign.name} - {timezone.now().date()}",
            topic=campaign.topic,
            description=campaign.generation_instructions,
            lifecycle_state='draft'
        )
        
        execution.content = content
        execution.save(update_fields=['content', 'updated_at'])
        
        # Step 2: Create initial research request if research instructions provided
        if campaign.research_instructions:
            ContentCreationRequest.objects.create(
                content=content,
                user=campaign.owner,
                topic=campaign.topic,
                instructions=campaign.research_instructions,
                status='pending'
            )
        
        # Step 3: Generate content using GenerationService
        execution.status = 'generating'
        execution.save(update_fields=['status', 'updated_at'])
        
        gen_service = GenerationService()
        gen_result = gen_service.generate_content(
            content_id=content.id,
            user=campaign.owner,
            topic=campaign.topic,
            generation_instructions=campaign.generation_instructions,
            provider_name='default'  # Use configured default provider
        )
        
        if not gen_result.get('success'):
            raise Exception(f"Generation failed: {gen_result.get('error', 'Unknown error')}")
        
        content.refresh_from_db()
        if not content.current_version:
            raise Exception("Generation did not create a content version")
        
        # Step 4: Run Review #1
        execution.status = 'reviewing'
        execution.save(update_fields=['status', 'updated_at'])
        
        review_service = ReviewService()
        review_result = review_service.execute_review(
            content_version_id=content.current_version.id,
            stage=1,
            provider_name='default'
        )
        
        if not review_result.get('success'):
            raise Exception(f"Review #1 failed: {review_result.get('error', 'Unknown error')}")
        
        review = review_result.get('review')
        
        # Step 5: If review needs revision, attempt correction (bounded to MAX_AUTOMATED_REVISIONS)
        correction_count = 0
        max_corrections = 2  # FR-021: Bounded AI Revision
        
        while review and review.status == 'needs_revision' and correction_count < max_corrections:
            correction_service = CorrectionService()
            correction_result = correction_service.execute_correction(
                content_id=content.id,
                review_id=review.id,
                user=campaign.owner,
                provider_name='default'
            )
            
            if not correction_result.get('success'):
                break  # Stop correction attempts on failure
            
            content.refresh_from_db()
            correction_count += 1
            
            # Re-review after correction (Review #2)
            review_result = review_service.execute_review(
                content_version_id=content.current_version.id,
                stage=2,
                provider_name='default'
            )
            
            if not review_result.get('success'):
                break
            
            review = review_result.get('review')
        
        # Step 6: Mark execution complete and send notification
        # Content is now in a reviewable state but NOT auto-approved
        # User must manually approve before publishing (FR-025: Manual Approval)
        content.lifecycle_state = 'pending_review'
        content.save(update_fields=['lifecycle_state', 'updated_at'])
        
        execution.status = 'completed'
        execution.completed_at = timezone.now()
        execution.save(update_fields=['status', 'completed_at', 'updated_at'])
        
        # Update campaign stats
        campaign.execution_count += 1
        campaign.success_count += 1
        campaign.last_executed = timezone.now()
        campaign.save(update_fields=[
            'execution_count', 'success_count', 'last_executed', 'updated_at'
        ])
        
        # Send success notification
        from content.services.notification_service import NotificationService
        NotificationService.create_notification(
            user=campaign.owner,
            notification_type='campaign_execution_success',
            title=f'Campaign "{campaign.name}" executed successfully',
            message=f'New content "{content.title}" has been generated and is ready for review.',
            content=content,
            campaign=campaign,
            send_email=True
        )
        
        # Schedule next execution
        _schedule_next_execution(campaign)
        
        return {
            'success': True,
            'content_id': content.id,
            'execution_id': execution.id,
            'correction_count': correction_count,
            'final_review_status': review.status if review else 'unknown'
        }
        
    except Exception as e:
        # Record failure
        execution.status = 'failed'
        execution.error_message = str(e)
        execution.error_type = type(e).__name__
        execution.completed_at = timezone.now()
        execution.save(update_fields=[
            'status', 'error_message', 'error_type', 'completed_at', 'updated_at'
        ])
        
        campaign.failure_count += 1
        campaign.last_error = str(e)
        campaign.save(update_fields=['failure_count', 'last_error', 'updated_at'])
        
        # Send failure notification
        from content.services.notification_service import NotificationService
        NotificationService.create_notification(
            user=campaign.owner,
            notification_type='campaign_execution_failure',
            title=f'Campaign "{campaign.name}" execution failed',
            message=f'Campaign execution failed: {str(e)}',
            campaign=campaign,
            send_email=True
        )
        
        # Retry with exponential backoff for transient failures
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'execution_id': execution.id if execution.id else None
        }


@shared_task
def schedule_due_campaigns():
    """
    Find active campaigns due for execution and queue them.
    
    Runs every minute via Celery Beat. Creates execution records
    and queues execute_campaign_task for each due campaign.
    """
    from content.models import Campaign
    
    now = timezone.now()
    
    due_campaigns = Campaign.objects.filter(
        status='active',
        next_execution__lte=now
    )
    
    queued_count = 0
    for campaign in due_campaigns:
        # Atomic claim: set next_execution to future to prevent duplicate queuing
        with transaction.atomic():
            campaign = Campaign.objects.select_for_update().get(id=campaign.id)
            if campaign.next_execution and campaign.next_execution <= now:
                # Queue task
                execute_campaign_task.delay(campaign.id)
                
                # Temporarily set next_execution to prevent re-queuing
                # Will be recalculated after successful execution
                campaign.next_execution = now + timedelta(days=1)
                campaign.save(update_fields=['next_execution', 'updated_at'])
                
                queued_count += 1
    
    return {'queued': queued_count}


def _schedule_next_execution(campaign):
    """Calculate and set next execution time based on frequency."""
    from content.models import Campaign
    
    if not campaign.start_date:
        return
    
    now = timezone.now()
    
    # Calculate next execution based on frequency
    frequency_map = {
        'daily': timedelta(days=1),
        'weekly': timedelta(weeks=1),
        'biweekly': timedelta(weeks=2),
        'monthly': timedelta(days=30),
    }
    
    delta = frequency_map.get(campaign.frequency, timedelta(weeks=1))
    next_execution = now + delta
    
    # Check if past end_date
    if campaign.end_date and next_execution.date() > campaign.end_date:
        campaign.status = 'completed'
        campaign.next_execution = None
    else:
        campaign.next_execution = next_execution
    
    campaign.save(update_fields=['status', 'next_execution', 'updated_at'])
