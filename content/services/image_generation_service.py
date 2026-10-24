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
            logger.error(f"Image generation failed: {gen_result.error}")
            return {
                'success': False,
                'error': f"AI image generation failed: {gen_result.error}",
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
            logger.error(f"Failed to save generated image: {e}")
            return {
                'success': False,
                'error': f"Failed to save generated image: {str(e)}",
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
