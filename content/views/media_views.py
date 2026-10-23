"""
Media management views (FR-039).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from content.models import Media, Content
from content.services.media_service import MediaService


@login_required
def media_list(request):
    """List all media files for the current user."""
    media_files = Media.objects.filter(owner=request.user).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(media_files, 24)  # 24 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'page_title': 'Media Library'
    }
    return render(request, 'content/media/list.html', context)


@login_required
def media_detail(request, pk):
    """Show media file details."""
    media = get_object_or_404(Media, id=pk, owner=request.user)
    
    context = {
        'media': media,
        'page_title': f'Media: {media.file_name}'
    }
    return render(request, 'content/media/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def media_upload(request):
    """Upload a new media file."""
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'No file uploaded.')
            return render(request, 'content/media/upload.html')
        
        uploaded_file = request.FILES['file']
        content_id = request.POST.get('content_id')
        
        # Get content if specified
        content = None
        if content_id:
            try:
                content = Content.objects.get(id=content_id, owner=request.user)
            except Content.DoesNotExist:
                messages.error(request, 'Invalid content specified.')
                return render(request, 'content/media/upload.html')
        
        # Upload via service
        result = MediaService.upload_media(
            user=request.user,
            uploaded_file=uploaded_file,
            content=content
        )
        
        if result['success']:
            media = result['media']
            messages.success(request, f'File "{media.file_name}" uploaded successfully.')
            return redirect('content:media_detail', pk=media.id)
        else:
            messages.error(request, f'Upload failed: {result["error"]}')
    
    # Get user's content for optional association
    recent_content = Content.objects.filter(owner=request.user).order_by('-created_at')[:10]
    
    context = {
        'recent_content': recent_content,
        'page_title': 'Upload Media'
    }
    return render(request, 'content/media/upload.html', context)


@login_required
@require_http_methods(["POST"])
def media_delete(request, pk):
    """Delete a media file."""
    media = get_object_or_404(Media, id=pk, owner=request.user)
    
    try:
        file_name = media.file_name
        # Delete file from storage
        if media.file:
            media.file.delete()
        media.delete()
        
        messages.success(request, f'Media "{file_name}" deleted.')
        return redirect('content:media_list')
    except Exception as e:
        messages.error(request, f'Error deleting media: {str(e)}')
        return redirect('content:media_detail', pk=media.id)
