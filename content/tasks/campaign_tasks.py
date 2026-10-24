"""Idempotent campaign content and media pipeline tasks."""
from datetime import timedelta
from uuid import uuid4

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone


@shared_task(bind=True, max_retries=2)
def execute_campaign_task(self, campaign_id, execution_key=None):
    from content.models import Campaign, CampaignExecution, Content
    from content.services.automated_post_orchestration import AutomatedPostOrchestrationService
    from content.services.correction_service import ContentCorrectionService
    from content.services.generation_service import ContentGenerationService
    from research.models import ContentCreationRequest
    from research.services.collection_service import ResearchCollectionService

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return {'success': False, 'error_type': 'not_found', 'error': 'Campaign not found.'}

    execution_key = execution_key or f"celery:{self.request.id or uuid4()}"
    with transaction.atomic():
        execution, created = CampaignExecution.objects.get_or_create(
            execution_key=execution_key,
            defaults={
                'campaign': campaign,
                'scheduled_time': timezone.now(),
                'started_at': timezone.now(),
                'status': 'researching',
            },
        )
        execution = CampaignExecution.objects.select_for_update(of=('self',)).select_related('campaign', 'content').get(pk=execution.pk)
        if execution.campaign_id != campaign.pk:
            return {'success': False, 'error_type': 'idempotency_conflict', 'error': 'Execution key is already used by another campaign.'}
        if execution.status == 'completed' and execution.image_media_id:
            return {'success': True, 'duplicate': True, 'execution_id': execution.pk, 'content_id': execution.content_id}
        if (
            not created
            and self.request.retries == 0
            and execution.status in {'researching', 'generating', 'reviewing'}
            and execution.started_at
            and execution.started_at > timezone.now() - timedelta(minutes=15)
        ):
            return {'success': True, 'already_running': True, 'execution_id': execution.pk}
        execution.started_at = timezone.now()
        execution.status = 'researching'
        execution.save(update_fields=['started_at', 'status', 'updated_at'])

    try:
        if not execution.content_id:
            with transaction.atomic():
                execution = CampaignExecution.objects.select_for_update(of=('self',)).get(pk=execution.pk)
                if execution.content_id:
                    content = execution.content
                else:
                    content = Content.objects.create(
                        owner=campaign.owner,
                        title=f"{campaign.name} - {timezone.localdate().isoformat()}",
                        topic=campaign.topic,
                        description=campaign.generation_instructions,
                        lifecycle_state='draft',
                    )
                    execution.content = content
                    execution.save(update_fields=['content', 'updated_at'])
        else:
            content = execution.content

        request_id = execution.execution_data.get('creation_request_id')
        creation_request = ContentCreationRequest.objects.filter(pk=request_id, user=campaign.owner).first() if request_id else None
        if not creation_request:
            with transaction.atomic():
                execution = CampaignExecution.objects.select_for_update(of=('self',)).get(pk=execution.pk)
                request_id = execution.execution_data.get('creation_request_id')
                creation_request = ContentCreationRequest.objects.filter(pk=request_id, user=campaign.owner).first() if request_id else None
                if not creation_request:
                    creation_request = ContentCreationRequest.create_from_profile(
                        user=campaign.owner,
                        content=content,
                        overrides={
                            'topics': [campaign.topic],
                            'specific_query': campaign.research_instructions or campaign.topic,
                            'source_categories': ['news'],
                        },
                    )
                    execution.execution_data = {**execution.execution_data, 'creation_request_id': creation_request.pk}
                    execution.save(update_fields=['execution_data', 'updated_at'])

        if not creation_request.research_results.exists():
            creation_request.status = 'researching'
            creation_request.save(update_fields=['status', 'updated_at'])
            collected = ResearchCollectionService.collect(creation_request)
            if not collected['success']:
                raise RuntimeError(creation_request.error_message or 'Campaign research returned no sources.')

        version = content.current_version
        latest_review = version.reviews.order_by('-stage', '-created_at').first() if version else None
        if not latest_review:
            execution.status = 'generating'
            execution.save(update_fields=['status', 'updated_at'])
            generated = ContentGenerationService.generate_draft_for_request(
                creation_request_id=creation_request.pk,
                user=campaign.owner,
                custom_instructions=campaign.generation_instructions,
            )
            if not generated.get('success'):
                raise RuntimeError('Content generation service returned failure.')
            content.refresh_from_db()
            version = content.current_version
            latest_review = version.reviews.order_by('-stage', '-created_at').first() if version else None

        corrections = 0
        while latest_review and latest_review.status != 'passed' and corrections < 2:
            execution.status = 'reviewing'
            execution.save(update_fields=['status', 'updated_at'])
            corrected = ContentCorrectionService.apply_bounded_correction(content.pk, campaign.owner)
            if not corrected.get('success'):
                break
            corrections += 1
            content.refresh_from_db()
            version = content.current_version
            latest_review = version.reviews.order_by('-stage', '-created_at').first()

        if not latest_review or latest_review.status != 'passed':
            raise RuntimeError('Campaign content did not pass mandatory AI quality review after bounded correction.')

        content.refresh_from_db()
        if content.lifecycle_state == 'in_progress':
            content.lifecycle_state = 'pending_review'
            content.save(update_fields=['lifecycle_state', 'updated_at'])

        image_result = AutomatedPostOrchestrationService.generate_image(execution.pk)
        if not image_result.get('success'):
            raise RuntimeError('Image generation service returned failure.')
        submit_to_buffer_task.delay(execution.pk)

        execution.status = 'completed'
        execution.completed_at = timezone.now()
        execution.error_message = ''
        execution.error_type = ''
        execution.save(update_fields=['status', 'completed_at', 'error_message', 'error_type', 'updated_at'])
        execution.execution_data = {**execution.execution_data, 'correction_count': corrections}
        execution.save(update_fields=['execution_data', 'updated_at'])

        with transaction.atomic():
            execution = CampaignExecution.objects.select_for_update(of=('self',)).get(pk=execution.pk)
            if not execution.execution_data.get('campaign_counted'):
                Campaign.objects.filter(pk=campaign.pk).update(
                    execution_count=F('execution_count') + 1,
                    success_count=F('success_count') + 1,
                    last_executed=timezone.now(),
                )
                execution.execution_data = {**execution.execution_data, 'campaign_counted': True}
                execution.save(update_fields=['execution_data', 'updated_at'])

        from content.services.notification_service import NotificationService
        NotificationService.create_notification(
            user=campaign.owner,
            notification_type='campaign_execution_success',
            title=f'Campaign "{campaign.name}" generated content',
            message=f'"{content.title}" passed AI review. Human text approval and the configured image approval are still enforced before publishing.',
            content=content,
            campaign=campaign,
            send_email=True,
        )
        _schedule_next_execution(campaign)
        return {
            'success': True,
            'content_id': content.pk,
            'execution_id': execution.pk,
            'correction_count': corrections,
            'final_review_status': latest_review.status,
            'pipeline_state': image_result.get('state'),
        }
    except Exception as exc:
        execution.refresh_from_db()
        execution.retry_count += 1
        execution.error_message = 'Campaign execution failed during a workflow step. Inspect its error type and retry status.'
        execution.error_type = type(exc).__name__
        execution.save(update_fields=['retry_count', 'error_message', 'error_type', 'updated_at'])
        if self.request.retries < self.max_retries:
            raise self.retry(exc=RuntimeError('Campaign workflow step failed.'), countdown=60 * (2 ** self.request.retries))
        with transaction.atomic():
            execution = CampaignExecution.objects.select_for_update(of=('self',)).get(pk=execution.pk)
            execution.status = 'failed'
            execution.completed_at = timezone.now()
            if not execution.execution_data.get('failure_counted'):
                Campaign.objects.filter(pk=campaign.pk).update(
                    failure_count=F('failure_count') + 1,
                    last_error='Campaign execution failed; inspect execution error type.',
                )
                execution.execution_data = {**execution.execution_data, 'failure_counted': True}
            execution.save(update_fields=['status', 'completed_at', 'execution_data', 'updated_at'])
        from content.services.notification_service import NotificationService
        NotificationService.create_notification(
            user=campaign.owner,
            notification_type='campaign_execution_failure',
            title=f'Campaign "{campaign.name}" execution failed',
            message=f'Campaign execution {execution.pk} failed. Inspect its error type and retry status.',
            campaign=campaign,
            send_email=True,
        )
        return {'success': False, 'error': 'Campaign execution failed during a workflow step.', 'error_type': type(exc).__name__, 'execution_id': execution.pk}


@shared_task(max_retries=0)
def submit_to_buffer_task(execution_id):
    """One-shot submit; ambiguous outcomes are recorded and must not be retried blindly."""
    from content.services.automated_post_orchestration import AutomatedPostOrchestrationService
    return AutomatedPostOrchestrationService.submit_to_buffer(execution_id)


@shared_task
def schedule_due_campaigns():
    from content.models import Campaign

    now = timezone.now()
    queued = 0
    for candidate in Campaign.objects.filter(status='active', next_execution__lte=now):
        with transaction.atomic():
            campaign = Campaign.objects.select_for_update().get(pk=candidate.pk)
            due_at = campaign.next_execution
            if not due_at or due_at > now:
                continue
            key = f"scheduled:{campaign.pk}:{due_at.isoformat()}"
            execute_campaign_task.delay(campaign.pk, execution_key=key)
            campaign.next_execution = now + timedelta(days=1)
            campaign.save(update_fields=['next_execution', 'updated_at'])
            queued += 1
    return {'queued': queued}


def _schedule_next_execution(campaign):
    from content.models import Campaign
    if not campaign.start_date:
        return
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if campaign.status != 'active':
            return
        delta = {
            'daily': timedelta(days=1),
            'weekly': timedelta(weeks=1),
            'biweekly': timedelta(weeks=2),
            'monthly': timedelta(days=30),
        }.get(campaign.frequency, timedelta(weeks=1))
        next_execution = timezone.now() + delta
        if campaign.end_date and next_execution.date() > campaign.end_date:
            campaign.status = 'completed'
            campaign.next_execution = None
        else:
            campaign.next_execution = next_execution
        campaign.save(update_fields=['status', 'next_execution', 'updated_at'])
