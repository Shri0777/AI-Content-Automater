from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from content.models import Campaign, CampaignExecution, Content, ContentReview, ContentVersion, Media, PublishingPreparation
from content.services.automated_post_orchestration import AutomatedPostOrchestrationService
from content.services.buffer_service import BufferPublishingService
from content.services.publishing_orchestrator import BufferPublishingOrchestrator
from content.tasks.campaign_tasks import execute_campaign_task

User = get_user_model()


class AutomatedPostOrchestrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pipeline-user', password='test-password')
        self.campaign = Campaign.objects.create(
            owner=self.user,
            name='Pipeline campaign',
            topic='Evidence-based Django updates',
            generation_instructions='Write a useful update.',
            start_date=date.today(),
            image_approval_required=True,
            target_platforms=['buffer-channel-1'],
        )
        self.content = Content.objects.create(
            owner=self.user,
            title='Django update',
            topic='Django',
            lifecycle_state='pending_review',
        )
        self.version = ContentVersion.create_initial_version(
            self.content, self.user,
            'Django adds useful improvements for application developers in the latest release.',
        )
        self.content.current_version = self.version
        self.content.save(update_fields=['current_version'])
        self.review = ContentReview.objects.create(
            content_version=self.version,
            stage=1,
            status='passed',
            score=0.9,
            summary='Review passed.',
        )
        self.execution = CampaignExecution.objects.create(
            campaign=self.campaign,
            content=self.content,
            execution_key='test-execution-1',
            scheduled_time=self.content.created_at,
            status='completed',
            execution_data={'image_version_id': self.version.pk},
        )

    def make_media(self):
        return Media.objects.create(
            owner=self.user,
            content=self.content,
            file_name='generated.png',
            file_size=128,
            mime_type='image/png',
            is_validated=True,
        )

    def test_prompt_is_derived_from_final_reviewed_text_and_media_is_linked(self):
        media = self.make_media()
        with patch('content.services.image_generation_service.ImageGenerationService.generate_image_for_content', return_value={'success': True, 'media': media}) as generate:
            result = AutomatedPostOrchestrationService.generate_image(self.execution.pk)

        self.assertTrue(result['success'], msg=result)
        self.assertIn(self.version.content_text[:120], generate.call_args.kwargs['prompt'])
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.image_media_id, media.pk)
        self.assertEqual(media.approval_status, 'pending')

    def test_image_generation_failure_is_recorded(self):
        with patch('content.services.image_generation_service.ImageGenerationService.generate_image_for_content', return_value={'success': False, 'error': 'provider unavailable', 'error_type': 'provider_error'}):
            result = AutomatedPostOrchestrationService.generate_image(self.execution.pk)
        self.assertFalse(result['success'])
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.execution_data['pipeline_state'], 'image_failed')
        self.assertEqual(self.execution.error_type, 'provider_error')

    def test_duplicate_image_generation_reuses_existing_media(self):
        media = self.make_media()
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        with patch('content.services.image_generation_service.ImageGenerationService.generate_image_for_content') as generate:
            result = AutomatedPostOrchestrationService.generate_image(self.execution.pk)
        self.assertTrue(result['duplicate'])
        generate.assert_not_called()

    def test_image_approval_blocks_submission(self):
        media = self.make_media()
        media.approval_status = 'pending'
        media.save(update_fields=['file', 'approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])

        with patch('content.services.buffer_service.BufferPublishingService.get_profiles') as profiles:
            result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertEqual(result['error_type'], 'image_approval_required')
        profiles.assert_not_called()

    def test_rejected_image_never_reenters_approval_or_publish(self):
        media = self.make_media()
        media.approval_status = 'rejected'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])
        with patch('content.services.buffer_service.BufferPublishingService.get_profiles') as profiles:
            result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertEqual(result['error_type'], 'image_rejected')
        profiles.assert_not_called()

    def test_text_edit_invalidates_the_linked_campaign_image(self):
        media = self.make_media()
        media.approval_status = 'approved'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        edited_version = ContentVersion.create_next_version(
            self.content, self.user, 'A materially edited post with enough words to pass review.'
        )
        edited_version.is_approved = True
        edited_version.save(update_fields=['is_approved'])
        self.content.current_version = edited_version
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['current_version', 'lifecycle_state'])
        ContentReview.objects.create(content_version=edited_version, status='passed', summary='Passed.')
        result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertEqual(result['error_type'], 'stale_image')

    def test_shared_publisher_blocks_campaign_without_image_approval(self):
        media = self.make_media()
        media.approval_status = 'pending'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])
        with patch('content.services.publishing_orchestrator.BufferPublishingService') as buffer_service:
            result = BufferPublishingOrchestrator.execute_publishing(
                self.content.pk, self.user, ['buffer-channel-1']
            )
        self.assertEqual(result['error_type'], 'image_approval_required')
        buffer_service.assert_not_called()

    def test_shared_publisher_requires_final_validation_for_campaign_content(self):
        media = self.make_media()
        media.approval_status = 'approved'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])
        result = BufferPublishingOrchestrator.execute_publishing(
            self.content.pk, self.user, ['buffer-channel-1']
        )
        self.assertEqual(result['error_type'], 'final_validation_required')

    @override_settings(MEDIA_URL='https://cdn.example.com/media/')
    def test_shared_publisher_attaches_the_approved_campaign_image(self):
        self.campaign.publish_immediately = True
        self.campaign.save(update_fields=['publish_immediately'])
        media = self.make_media()
        media.file.name = 'media/generated.png'
        media.approval_status = 'approved'
        media.save(update_fields=['file', 'approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'ready_to_publish'
        self.content.save(update_fields=['lifecycle_state'])
        PublishingPreparation.objects.create(
            content=self.content,
            content_version=self.version,
            prepared_by=self.user,
            target_platforms=['linkedin'],
            status='prepared',
            prepared_payload={'linkedin': {'text': self.version.content_text}},
        )
        with patch('content.services.publishing_orchestrator.BufferPublishingService.is_configured', return_value=True), \
             patch('content.services.publishing_orchestrator.BufferPublishingService.get_profiles', return_value=[{'id': 'buffer-channel-1'}]), \
             patch('content.services.publishing_orchestrator.BufferPublishingService.create_update', return_value={'success': True, 'updates': [{'id': 'post-1', 'status': 'pending'}]}) as create_update:
            result = BufferPublishingOrchestrator.execute_publishing(
                self.content.pk,
                self.user,
                ['buffer-channel-1'],
                client_idempotency_key=f'campaign-execution-{self.execution.pk}',
            )
        self.assertTrue(result['success'])
        self.assertEqual(create_update.call_args.kwargs['image_urls'], [media.file.url])

    def test_human_text_approval_is_required_even_without_image_approval(self):
        self.campaign.image_approval_required = False
        self.campaign.save(update_fields=['image_approval_required'])
        media = self.make_media()
        media.approval_status = 'not_required'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertEqual(result['error_type'], 'approval_required')

    @override_settings(MEDIA_URL='https://cdn.example.com/media/')
    def test_no_image_approval_progresses_to_final_validation_but_not_unapproved_publish(self):
        self.campaign.image_approval_required = False
        self.campaign.save(update_fields=['image_approval_required'])
        media = self.make_media()
        media.file.name = 'media/generated.png'
        media.approval_status = 'not_required'
        media.save(update_fields=['file', 'approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])
        with patch('content.services.buffer_service.BufferPublishingService.get_profiles', return_value=[{'id': 'buffer-channel-1', 'service': 'linkedin'}]), \
             patch('content.services.publishing_service.PublishingPreparationService.prepare_content', return_value={'success': True}) as prepare, \
             patch('content.services.publishing_orchestrator.BufferPublishingOrchestrator.execute_publishing') as publish:
            result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertTrue(result['success'], msg=result)
        self.assertTrue(result['pending'])
        self.assertEqual(result['state'], 'ready_to_publish')
        prepare.assert_called_once()
        publish.assert_not_called()

    def test_image_approval_route_is_owner_scoped_and_post_only(self):
        media = self.make_media()
        media.approval_status = 'pending'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse('content:campaign_image_approve', args=[self.execution.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 405)
        detail_url = reverse('content:campaign_detail', args=[self.campaign.pk])
        client.get(detail_url)
        csrf_token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url).status_code, 403)
        response = client.post(url, HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(response.status_code, 302)
        media.refresh_from_db()
        self.assertEqual(media.approval_status, 'approved')

        other = User.objects.create_user(username='pipeline-other', password='test-password')
        client.force_login(other)
        self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=csrf_token).status_code, 404)

    @override_settings(MEDIA_URL='https://cdn.example.com/media/')
    def test_missing_public_image_url_fails_closed(self):
        media = self.make_media()
        media.file.name = 'media/generated.png'
        media.approval_status = 'approved'
        media.save(update_fields=['approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])
        with patch('content.services.buffer_service.BufferPublishingService.get_profiles', return_value=[{'id': 'buffer-channel-1', 'service': 'linkedin'}]), \
             patch('content.services.publishing_service.PublishingPreparationService.prepare_content', return_value={'success': True}), \
             patch('content.services.publishing_orchestrator.BufferPublishingOrchestrator.execute_publishing') as publish:
            result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertEqual(result['error_type'], 'public_media_url_required')
        publish.assert_not_called()

    @override_settings(BUFFER_ACCESS_TOKEN='test-token')
    def test_buffer_rejects_non_public_image_url_without_posting(self):
        service = BufferPublishingService(access_token='test-token')
        with patch.object(service, '_is_reachable_image_url', return_value=True), patch('content.services.buffer_service.requests.post') as post:
            result = service.create_update(['channel'], 'A reviewed post', image_urls=['https://127.0.0.1/private.png'])
        self.assertEqual(result['error_type'], 'invalid_image_url')
        post.assert_not_called()

    def test_buffer_payload_contains_the_image_asset(self):
        service = BufferPublishingService(access_token='test-token')
        response = type('Response', (), {
            'status_code': 200,
            'json': lambda _self: {'data': {'createPost': {'post': {'id': 'post-1', 'text': 'Reviewed text', 'status': 'pending'}}}},
        })()
        image_url = 'https://cdn.example.com/images/approved.png'
        with patch.object(service, '_is_public_https_url', return_value=True), \
             patch.object(service, '_is_reachable_image_url', return_value=True), \
             patch('content.services.buffer_service.requests.post', return_value=response) as post:
            result = service.create_update(['buffer-channel-1'], 'Reviewed text', image_urls=[image_url])
        self.assertTrue(result['success'])
        payload = post.call_args.kwargs['json']['variables']['input']
        self.assertEqual(payload['text'], 'Reviewed text')
        self.assertEqual(payload['assets'], [{'image': {'url': image_url}}])

    @override_settings(MEDIA_URL='https://cdn.example.com/media/')
    def test_buffer_failure_is_recorded_without_retrying_submission(self):
        self.campaign.publish_immediately = True
        self.campaign.save(update_fields=['publish_immediately'])
        media = self.make_media()
        media.file.name = 'media/generated.png'
        media.approval_status = 'approved'
        media.save(update_fields=['file', 'approval_status'])
        self.execution.image_media = media
        self.execution.save(update_fields=['image_media'])
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])
        self.content.lifecycle_state = 'approved'
        self.content.save(update_fields=['lifecycle_state'])
        with patch('content.services.buffer_service.BufferPublishingService.get_profiles', return_value=[{'id': 'buffer-channel-1', 'service': 'linkedin'}]), \
             patch('content.services.publishing_service.PublishingPreparationService.prepare_content', return_value={'success': True}), \
             patch('content.services.publishing_orchestrator.BufferPublishingOrchestrator.execute_publishing', return_value={'success': False, 'error_type': 'transient_failure', 'error': 'Buffer unavailable'}):
            result = AutomatedPostOrchestrationService.submit_to_buffer(self.execution.pk)
        self.assertFalse(result['success'])
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.execution_data['pipeline_state'], 'publish_failed')


class CampaignTaskIdempotencyTests(TestCase):
    def test_retry_key_reuses_execution_content_and_image(self):
        user = User.objects.create_user(username='task-user', password='test-password')
        campaign = Campaign.objects.create(
            owner=user,
            name='Retry campaign',
            topic='Testing',
            generation_instructions='Write a reviewed post.',
            start_date=date.today(),
        )

        def generate_text(*, creation_request_id, user, custom_instructions=None):
            from research.models import ContentCreationRequest
            request = ContentCreationRequest.objects.get(pk=creation_request_id)
            content = request.content
            version = ContentVersion.create_initial_version(content, user, 'A sufficiently long reviewed campaign post.')
            content.current_version = version
            content.save(update_fields=['current_version'])
            ContentReview.objects.create(content_version=version, status='passed', summary='Passed.')
            return {'success': True, 'version': version}

        def make_image(execution_id):
            execution = CampaignExecution.objects.get(pk=execution_id)
            media = Media.objects.create(
                owner=user, content=execution.content, file_name='campaign.png',
                file_size=100, mime_type='image/png', is_validated=True,
                approval_status='pending',
            )
            execution.image_media = media
            execution.execution_data = {**execution.execution_data, 'image_version_id': execution.content.current_version_id}
            execution.save(update_fields=['image_media', 'execution_data'])
            return {'success': True, 'media': media, 'state': 'pending_image_approval'}

        with patch('research.services.collection_service.ResearchCollectionService.collect', return_value={'success': True, 'saved_count': 1, 'errors': []}), \
             patch('content.services.generation_service.ContentGenerationService.generate_draft_for_request', side_effect=generate_text) as generate, \
             patch('content.services.automated_post_orchestration.AutomatedPostOrchestrationService.generate_image', side_effect=make_image) as image, \
             patch('content.tasks.campaign_tasks.submit_to_buffer_task.delay'), \
             patch('content.services.notification_service.NotificationService.create_notification'):
            first = execute_campaign_task.run(campaign.pk, execution_key='stable-retry-key')
            second = execute_campaign_task.run(campaign.pk, execution_key='stable-retry-key')

        self.assertTrue(first['success'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(CampaignExecution.objects.filter(execution_key='stable-retry-key').count(), 1)
        generate.assert_called_once()
        image.assert_called_once()

