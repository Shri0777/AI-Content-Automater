"""Idempotent campaign image-generation and Buffer publishing workflow."""
import logging
from urllib.parse import urlsplit

from django.db import transaction

from content.models import CampaignExecution


class AutomatedPostOrchestrationService:
    @staticmethod
    def build_image_prompt(final_text: str) -> str:
        """Build the image brief from the reviewed post, not a generic campaign prompt."""
        body = (final_text or '').strip()
        if not body:
            raise ValueError('Reviewed post text is required to create an image prompt.')
        return (
            'Create a polished, original editorial illustration for this social post. '
            'Depict its central subject accurately; do not add text, logos, or unsupported claims. '
            f'Post content: {body[:720]}'
        )

    @classmethod
    def generate_image(cls, execution_id: int) -> dict:
        from content.services.image_generation_service import ImageGenerationService

        with transaction.atomic():
            execution = (
                CampaignExecution.objects.select_for_update(of=('self',))
                .select_related('campaign', 'campaign__owner', 'content', 'content__current_version', 'image_media')
                .filter(pk=execution_id)
                .first()
            )
            if not execution or not execution.content:
                return {'success': False, 'error_type': 'not_found', 'error': 'Campaign execution was not found.'}
            if execution.image_media_id:
                return {
                    'success': True,
                    'duplicate': True,
                    'media': execution.image_media,
                    'state': execution.execution_data.get('pipeline_state'),
                }

            version = execution.content.current_version
            if not version or not version.content_text:
                return {'success': False, 'error_type': 'no_version', 'error': 'Final reviewed text is unavailable.'}
            review = version.reviews.order_by('-stage', '-created_at').first()
            if not review or review.status != 'passed':
                return {'success': False, 'error_type': 'review_required', 'error': 'A passing AI review is required before image generation.'}

            prompt = cls.build_image_prompt(version.content_text)
            result = ImageGenerationService.generate_image_for_content(
                content_id=execution.content_id,
                user=execution.campaign.owner,
                prompt=prompt,
            )
            if not result.get('success') or not result.get('media'):
                execution.execution_data = {**execution.execution_data, 'pipeline_state': 'image_failed'}
                execution.error_message = result.get('error', 'Image generation failed.')
                execution.error_type = result.get('error_type', 'image_generation_failed')
                execution.save(update_fields=['execution_data', 'error_message', 'error_type', 'updated_at'])
                return result

            media = result['media']
            if (
                media.owner_id != execution.campaign.owner_id
                or media.content_id != execution.content_id
                or not media.is_validated
                or not (media.mime_type or '').lower().startswith('image/')
            ):
                return {'success': False, 'error_type': 'invalid_media', 'error': 'Image service returned media that failed ownership or validation checks.'}
            execution.content.refresh_from_db(fields=['current_version'])
            if execution.content.current_version_id != version.pk:
                media.is_validated = False
                media.validation_errors = 'Generated from a content version that is no longer current.'
                media.save(update_fields=['is_validated', 'validation_errors'])
                execution.execution_data = {**execution.execution_data, 'pipeline_state': 'stale_image'}
                execution.save(update_fields=['execution_data', 'updated_at'])
                return {'success': False, 'error_type': 'stale_image', 'error': 'Content changed during image generation; the image was not attached to the campaign execution.'}
            media.approval_status = 'pending' if execution.campaign.image_approval_required else 'not_required'
            media.save(update_fields=['approval_status'])
            execution.image_media = media
            state = 'pending_image_approval' if execution.campaign.image_approval_required else 'awaiting_text_approval'
            execution.execution_data = {
                **execution.execution_data,
                'pipeline_state': state,
                'image_version_id': version.pk,
            }
            execution.save(update_fields=['image_media', 'execution_data', 'updated_at'])
            return {'success': True, 'media': media, 'state': state}

    @classmethod
    def submit_to_buffer(cls, execution_id: int) -> dict:
        """Run final validation and submit only after all approval gates are satisfied."""
        from content.services.buffer_service import BufferPublishingService
        from content.services.publishing_orchestrator import BufferPublishingOrchestrator
        from content.services.publishing_service import PublishingPreparationService

        execution = (
            CampaignExecution.objects.select_related(
                'campaign', 'campaign__owner', 'content', 'content__current_version', 'image_media'
            ).filter(pk=execution_id).first()
        )
        if not execution or not execution.content or not execution.image_media:
            return {'success': False, 'error_type': 'incomplete_pipeline', 'error': 'Generated campaign media is required.'}
        content = execution.content
        version = content.current_version
        media = execution.image_media
        if not version or not version.is_approved:
            execution.execution_data = {**execution.execution_data, 'pipeline_state': 'awaiting_text_approval'}
            execution.save(update_fields=['execution_data', 'updated_at'])
            return {'success': False, 'pending': True, 'error_type': 'approval_required', 'error': 'Human approval of the current text version is required.'}
        if execution.execution_data.get('image_version_id') != version.pk:
            execution.execution_data = {**execution.execution_data, 'pipeline_state': 'stale_image'}
            execution.save(update_fields=['execution_data', 'updated_at'])
            return {'success': False, 'error_type': 'stale_image', 'error': 'The campaign image was generated from a different text version. Generate a new campaign image before publishing.'}
        if media.approval_status == 'rejected':
            execution.execution_data = {**execution.execution_data, 'pipeline_state': 'image_rejected'}
            execution.save(update_fields=['execution_data', 'updated_at'])
            return {'success': False, 'error_type': 'image_rejected', 'error': 'The campaign image was rejected and cannot be submitted.'}
        if execution.campaign.image_approval_required and media.approval_status != 'approved':
            execution.execution_data = {**execution.execution_data, 'pipeline_state': 'pending_image_approval'}
            execution.save(update_fields=['execution_data', 'updated_at'])
            return {'success': False, 'pending': True, 'error_type': 'image_approval_required', 'error': 'Image approval is required before publishing.'}
        review = version.reviews.order_by('-stage', '-created_at').first()
        if not review or review.status != 'passed':
            return {'success': False, 'error_type': 'review_required', 'error': 'Current text version must pass AI review.'}

        try:
            image_url = media.file.url
        except (ValueError, OSError):
            return {'success': False, 'error_type': 'public_media_url_required', 'error': 'Media storage did not provide a publicly reachable image URL.'}
        parsed = urlsplit(image_url)
        if parsed.scheme != 'https' or not parsed.hostname:
            return {'success': False, 'error_type': 'public_media_url_required', 'error': 'Media storage must provide an absolute public HTTPS image URL.'}

        buffer = BufferPublishingService()
        try:
            profiles = buffer.get_profiles()
        except Exception:
            return {'success': False, 'error_type': 'destination_verification_failed', 'error': 'Could not verify Buffer destinations.'}
        requested = {str(value) for value in execution.campaign.target_platforms}
        selected = [profile for profile in profiles if str(profile.get('id')) in requested]
        if not requested or not selected:
            return {'success': False, 'error_type': 'missing_destination', 'error': 'Campaign must specify verified Buffer destination IDs.'}

        platform_names = []
        for profile in selected:
            name = str(profile.get('service') or 'generic').lower()
            platform_names.append(name if name in {'twitter', 'linkedin'} else 'generic')
        validation = PublishingPreparationService.prepare_content(
            content_id=content.pk,
            user=execution.campaign.owner,
            target_platforms=sorted(set(platform_names)),
        )
        if not validation.get('success'):
            return {'success': False, 'error_type': validation.get('error_type', 'validation_failed'), 'error': validation.get('error')}

        if not execution.campaign.publish_immediately:
            execution.execution_data = {**execution.execution_data, 'pipeline_state': 'ready_to_publish'}
            execution.save(update_fields=['execution_data', 'updated_at'])
            return {'success': True, 'pending': True, 'state': 'ready_to_publish'}

        execution.execution_data = {**execution.execution_data, 'pipeline_state': 'submitting_to_buffer'}
        execution.save(update_fields=['execution_data', 'updated_at'])
        result = BufferPublishingOrchestrator.execute_publishing(
            content_id=content.pk,
            user=execution.campaign.owner,
            profile_ids=[str(profile['id']) for profile in selected],
            mode='immediate',
            client_idempotency_key=f'campaign-execution-{execution.pk}',
            image_urls=[image_url],
        )
        ambiguous = any(item.get('status') == 'ambiguous' for item in result.get('results', []))
        state = 'ambiguous' if ambiguous else ('submitted' if result.get('success') else ('partially_submitted' if result.get('partial_success') else 'publish_failed'))
        execution.execution_data = {**execution.execution_data, 'pipeline_state': state}
        if not result.get('success'):
            execution.error_type = result.get('error_type', 'publishing_failed')
            execution.error_message = 'Buffer submission did not complete successfully; inspect publication status before retrying.'
        execution.save(update_fields=['execution_data', 'error_type', 'error_message', 'updated_at'])
        return result
