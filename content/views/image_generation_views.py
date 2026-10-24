"""
Image generation views for AI Content Automater.

Handles image generation requests for content using configured AI providers.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from content.models import Content
from content.services.image_generation_service import ImageGenerationService

logger = logging.getLogger(__name__)


@login_required
@require_POST
def generate_image_for_content(request, pk):
    """
    Generate a promotional image for a content piece using AI.
    
    POST /content/<pk>/generate-image/
    Form data: prompt (required), size, quality, style (optional)
    """
    content = get_object_or_404(Content, pk=pk, owner=request.user)
    
    # Extract parameters from POST
    prompt = request.POST.get('prompt', '').strip()
    size = request.POST.get('size', '1024x1024')
    quality = request.POST.get('quality', 'standard')
    style = request.POST.get('style', 'vivid')
    
    if not prompt:
        messages.error(request, 'Image generation prompt is required.')
        return redirect('content:detail', pk=pk)
    
    # Call image generation service
    result = ImageGenerationService.generate_image_for_content(
        content_id=content.pk,
        user=request.user,
        prompt=prompt,
        size=size,
        quality=quality,
        style=style
    )
    
    # Handle HTMX requests with partial response
    if request.headers.get('HX-Request'):
        if result['success']:
            media = result.get('media')
            return JsonResponse({
                'success': True,
                'media_id': media.pk,
                'media_url': media.file.url if media and media.file else None,
                'message': f'Image generated successfully by {result.get("provider", "AI provider")}.'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Image generation failed.'),
                'error_type': result.get('error_type', 'unknown')
            }, status=400)
    
    # Handle regular form submission
    if result['success']:
        messages.success(
            request,
            f'Image generated successfully by {result.get("provider", "AI provider")}. '
            f'Check the Media section below.'
        )
    else:
        error_msg = result.get('error', 'Image generation failed.')
        messages.error(request, error_msg)
    
    return redirect('content:detail', pk=pk)
