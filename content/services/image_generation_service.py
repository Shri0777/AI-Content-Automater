"""
Image generation service for AI Content Automater.

Generates promotional images for content using configured AI image providers (e.g., NVIDIA FLUX).
"""
import logging
from typing import Any, Dict, Optional
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from ai_providers.services.base_adapter import ProviderCapability
from ai_providers.services.validation_service import CredentialValidationService
from content.models import Content, Media
from content.services.platform_formats import (
    get_required_variants,
    is_supported_size,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ImageGenerationService:
    """
    Orchestrates AI-powered image generation for content.
    """
    
    @staticmethod
    def generate_image_for_content(
        content_id: int,
        user: Any,
        prompt: str,
        **generation_params
    ) -> Dict[str, Any]:
        """
        Generate a promotional image for a content piece.
        
        Args:
            content_id: PK of the Content record
            user: Authenticated user (ownership verified)
            prompt: Image generation prompt
            **generation_params: Additional parameters (size, quality, style, etc.)
            
        Returns:
            Dict with success, media, or error details.
        """
        # 1. Verify content ownership
        content = Content.objects.filter(pk=content_id, owner=user).first()
        if not content:
            return {
                'success': False,
                'error': 'Content not found or unauthorized.',
                'error_type': 'not_found'
            }
        
        # 2. Validate prompt
        if not prompt or not prompt.strip():
            return {
                'success': False,
                'error': 'Image prompt cannot be empty.',
                'error_type': 'invalid_prompt'
            }
        
        # 3. Resolve active AI image provider (user config with canonical env fallback)
        adapter, credential, model_name, endpoint = CredentialValidationService.get_active_provider_for_user(
            user=user,
            capability='image'
        )
        
        if not adapter or not credential:
            return {
                'success': False,
                'error': 'No active AI image provider configured. Please configure NVIDIA FLUX in AI Settings.',
                'error_type': 'no_provider'
            }
        
        # 4. Check if provider supports image generation
        if ProviderCapability.IMAGE_GENERATION not in adapter.supported_capabilities:
            return {
                'success': False,
                'error': f'{adapter.display_name} does not support image generation.',
                'error_type': 'unsupported_capability'
            }
        
        # 5. Generate image via provider adapter
        logger.info(f"Generating image for content {content_id} using {adapter.provider_name}")
        
        gen_result = adapter.generate_image(
            prompt=prompt.strip(),
            credential=credential,
            model_name=model_name,
            endpoint=endpoint,
            **generation_params
        )
        
        if not gen_result.success:
            logger.error('Image generation failed (%s).', gen_result.error_type or 'provider_error')
            return {
                'success': False,
                'error': 'AI image generation failed. Check provider configuration and try again.',
                'error_type': gen_result.error_type or 'generation_failed'
            }
        
        # 6. Store generated image as Media record
        try:
            pil_image = gen_result.content
            if not pil_image:
                return {
                    'success': False,
                    'error': 'Image generation succeeded but no image data returned.',
                    'error_type': 'malformed_response'
                }
            
            # Save PIL Image to BytesIO
            image_io = BytesIO()
            image_format = pil_image.format or 'PNG'
            pil_image.save(image_io, format=image_format)
            image_io.seek(0)
            
            # Determine filename
            safe_title = content.title[:50].replace(' ', '_').replace('/', '_')
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{safe_title}_{timestamp}.{image_format.lower()}"
            
            # Get metadata
            width, height = pil_image.size
            mime_type = f"image/{image_format.lower()}"
            if image_format.upper() == 'JPEG':
                mime_type = "image/jpeg"
            
            # Create Media record
            media = Media.objects.create(
                owner=user,
                content=content,
                file_name=filename,
                file_size=len(image_io.getvalue()),
                mime_type=mime_type,
                width=width,
                height=height,
                is_validated=True
            )
            
            # Save file through Django storage
            media.file.save(filename, ContentFile(image_io.getvalue()), save=True)
            
            logger.info(f"Image saved as Media {media.id} for content {content_id}")
            
            return {
                'success': True,
                'media_id': media.id,
                'media': media,
                'model_used': gen_result.model_used,
                'metadata': gen_result.metadata,
                'width': width,
                'height': height,
                'format': image_format,
                'file_size': len(image_io.getvalue())
            }
            
        except Exception as e:
            logger.error('Generated image storage failed (%s).', type(e).__name__)
            return {
                'success': False,
                'error': 'Generated image could not be saved. Check media storage and try again.',
                'error_type': 'storage_error'
            }
    
    @staticmethod
    def validate_image_prompt(prompt: str, max_length: int = 1000) -> Dict[str, Any]:
        """
        Validate an image generation prompt.
        
        Returns:
            Dict with valid: bool and error message if invalid.
        """
        if not prompt or not prompt.strip():
            return {
                'valid': False,
                'error': 'Prompt cannot be empty.'
            }
        
        if len(prompt) > max_length:
            return {
                'valid': False,
                'error': f'Prompt exceeds maximum length of {max_length} characters.'
            }
        
        # Check for potentially harmful content (basic check)
        forbidden_terms = ['nude', 'naked', 'explicit', 'nsfw']
        lower_prompt = prompt.lower()
        for term in forbidden_terms:
            if term in lower_prompt:
                return {
                    'valid': False,
                    'error': 'Prompt contains inappropriate content.'
                }
        
        return {'valid': True}

    @staticmethod
    def generate_poster_variants(
        content: Content,
        user: Any,
        brief: str,
        copy: str,
        destinations: list,
        brand_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate poster variants for the selected destinations.

        One variant is generated per unique image format group, so destinations
        that safely share a format produce a single asset. Each variant is
        stored as a Media record tagged with its intended platforms.

        Args:
            content: Content record to associate variants with.
            user: Authenticated content owner.
            brief: Original user brief.
            copy: Generated post copy.
            destinations: list of Buffer profile dicts (id + service).
            brand_context: Optional extra business context.

        Returns:
            Dict with 'success', list of 'variants', and any 'error'.
        """
        if not destinations:
            return {
                'success': False,
                'error': 'No destinations selected. Cannot generate poster variants.',
                'error_type': 'missing_destinations'
            }

        variants = get_required_variants(destinations)
        if not variants:
            return {
                'success': False,
                'error': 'No image formats could be resolved for the selected destinations.',
                'error_type': 'no_formats'
            }

        results = []
        for fmt in variants:
            size = fmt.size
            if not is_supported_size(size):
                results.append({
                    'format': fmt,
                    'success': False,
                    'error': f'Unsupported size {size}.',
                    'error_type': 'unsupported_size'
                })
                continue

            prompt = ImageGenerationService._build_poster_prompt(
                brief=brief,
                copy=copy,
                service=fmt.service,
                orientation=fmt.orientation,
                brand_context=brand_context,
            )

            try:
                gen_result = ImageGenerationService.generate_image_for_content(
                    content_id=content.pk,
                    user=user,
                    prompt=prompt,
                    size=size,
                    quality='standard',
                    style='natural',
                )

                if not gen_result.get('success', False):
                    results.append({
                        'format': fmt,
                        'media': None,
                        'success': False,
                        'error': gen_result.get('error', 'Image generation failed.'),
                        'error_type': gen_result.get('error_type', 'generation_failed')
                    })
                    continue

                generated_media = gen_result.get('media')
                if generated_media:
                    generated_media.platforms = [fmt.service]
                    generated_media.generation_state = 'generated'
                    generated_media.save(update_fields=['platforms', 'generation_state'])
                    results.append({
                        'format': fmt,
                        'media': generated_media,
                        'success': True,
                    })
                else:
                    results.append({
                        'format': fmt,
                        'media': None,
                        'success': False,
                        'error': 'No image data returned.',
                        'error_type': 'malformed_response'
                    })

            except Exception as exc:  # pragma: no cover - defensive
                logger.error('Poster variant generation failed for %s: %s', size, exc)
                results.append({
                    'format': fmt,
                    'media': None,
                    'success': False,
                    'error': 'Image generation failed.',
                    'error_type': 'unexpected_error'
                })

        any_success = any(r.get('success') for r in results)
        return {
            'success': any_success,
            'variants': results,
            'total': len(results),
            'successful_count': sum(1 for r in results if r.get('success')),
        }

    @staticmethod
    def retry_poster_variant(media: Media, user: Any) -> Dict[str, Any]:
        """
        Retry a single failed poster variant without touching other variants.

        Args:
            media: Media record in 'failed' state.
            user: Authenticated content owner.

        Returns:
            Dict with 'success' plus updated media or error details.
        """
        if media.generation_state != 'failed':
            return {
                'success': False,
                'error': 'Only failed poster variants can be retried.',
                'error_type': 'not_failed'
            }

        content = media.content
        brief = (content.brief or '').strip()
        copy = (content.current_version.content_text or '').strip() if content.current_version else ''

        from content.services.platform_formats import get_format_for_service
        svc = (media.platforms or ['unknown'])[0]
        fmt = get_format_for_service(svc)
        size = fmt.size

        if not is_supported_size(size):
            return {
                'success': False,
                'error': f'Unsupported size {size}.',
                'error_type': 'unsupported_size'
            }

        prompt = ImageGenerationService._build_poster_prompt(
            brief=brief,
            copy=copy,
            service=fmt.service,
            orientation=fmt.orientation,
        )

        try:
            gen_result = ImageGenerationService.generate_image_for_content(
                content_id=content.pk,
                user=user,
                prompt=prompt,
                size=size,
                quality='standard',
                style='natural',
            )

            if not gen_result.get('success', False):
                media.generation_state = 'failed'
                media.save(update_fields=['generation_state'])
                return {
                    'success': False,
                    'error': gen_result.get('error', 'Image generation failed.'),
                    'error_type': gen_result.get('error_type', 'generation_failed')
                }

            generated_media = gen_result.get('media')
            if generated_media:
                # Mark the old failed record and use the newly generated one.
                media.generation_state = 'failed'
                media.save(update_fields=['generation_state'])
                generated_media.platforms = media.platforms or [fmt.service]
                generated_media.generation_state = 'generated'
                generated_media.save(update_fields=['platforms', 'generation_state'])
                return {
                    'success': True,
                    'media': generated_media,
                    'format': fmt,
                }

            media.generation_state = 'failed'
            media.save(update_fields=['generation_state'])
            return {
                'success': False,
                'error': 'No image data returned.',
                'error_type': 'malformed_response'
            }

        except Exception as exc:  # pragma: no cover - defensive
            logger.error('Poster variant retry failed for media %s: %s', media.pk, exc)
            media.generation_state = 'failed'
            media.save(update_fields=['generation_state'])
            return {
                'success': False,
                'error': 'Image generation retry failed.',
                'error_type': 'unexpected_error'
            }

    @staticmethod
    def _build_poster_prompt(
        brief: str,
        copy: str,
        service: str,
        orientation: str,
        brand_context: Optional[str] = None
    ) -> str:
        """
        Derive an image-generation prompt from brief, copy, and format.

        The prompt is descriptive (scene/composition only) and does not attempt
        to render exact copy text, because the FLUX model is not verified to
        reproduce exact text reliably.
        """
        orientation_guide = {
            'square': 'square 1:1 composition',
            'landscape': 'wide landscape 16:9 composition',
            'portrait': 'tall portrait 9:16 composition',
        }.get(orientation, 'square 1:1 composition')

        prompt = (
            f"Professional social media poster for {service}, {orientation_guide}. "
            f"Based on the brief: {brief}. "
            f"Post message: {copy[:200]}. "
        )
        if brand_context:
            prompt += f"Brand context: {brand_context}. "
        prompt += (
            "Clean promotional visual, modern design, ample negative space for "
            "text overlay, high quality, no watermark, no legible text."
        )
        return prompt
