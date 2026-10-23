"""
Media Service for handling file uploads and validation (FR-039).

Provides secure file upload, validation, and association with content.
"""
import logging
import mimetypes
import os
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from content.models import Media

logger = logging.getLogger(__name__)

# Allowed MIME types for media uploads
ALLOWED_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'video/mp4',
    'video/quicktime',
}

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class MediaService:
    """
    Service for media file uploads and management.
    """
    
    @staticmethod
    def upload_media(
        user: Any,
        uploaded_file: UploadedFile,
        content=None
    ) -> Dict[str, Any]:
        """
        Upload and validate a media file.
        
        Args:
            user: User uploading the file
            uploaded_file: Django UploadedFile object
            content: Optional Content to associate with
            
        Returns:
            Dict with success flag and Media object or error details
        """
        try:
            # Validate file size
            if uploaded_file.size > MAX_FILE_SIZE:
                return {
                    'success': False,
                    'error': f'File size ({uploaded_file.size} bytes) exceeds maximum ({MAX_FILE_SIZE} bytes)',
                    'error_type': 'file_too_large'
                }
            
            # Validate MIME type
            mime_type = uploaded_file.content_type
            if mime_type not in ALLOWED_MIME_TYPES:
                return {
                    'success': False,
                    'error': f'File type {mime_type} is not allowed. Allowed types: {", ".join(ALLOWED_MIME_TYPES)}',
                    'error_type': 'invalid_mime_type'
                }
            
            # Generate safe filename
            original_name = uploaded_file.name
            safe_name = MediaService._make_safe_filename(original_name)
            
            # Create Media record
            media = Media.objects.create(
                owner=user,
                content=content,
                file=uploaded_file,
                file_name=safe_name,
                file_size=uploaded_file.size,
                mime_type=mime_type,
                is_validated=False
            )
            
            # Validate and extract metadata
            validation_result = MediaService._validate_and_extract_metadata(media)
            
            if validation_result['success']:
                media.is_validated = True
                media.validation_errors = ''
                
                # Update dimensions if image
                if validation_result.get('width'):
                    media.width = validation_result['width']
                    media.height = validation_result['height']
                
                media.save(update_fields=['is_validated', 'validation_errors', 'width', 'height'])
            else:
                media.is_validated = False
                media.validation_errors = validation_result.get('error', 'Unknown validation error')
                media.save(update_fields=['is_validated', 'validation_errors'])
            
            return {
                'success': True,
                'media': media,
                'validation': validation_result
            }
            
        except Exception as e:
            logger.error(f"Media upload failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    @staticmethod
    def _make_safe_filename(filename: str) -> str:
        """
        Generate a safe filename from user input.
        
        Args:
            filename: Original filename
            
        Returns:
            Safe filename
        """
        # Get base name and extension
        base, ext = os.path.splitext(filename)
        
        # Remove potentially dangerous characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        safe_base = ''.join(c for c in base if c in safe_chars)
        
        # Ensure we have something
        if not safe_base:
            safe_base = 'upload'
        
        # Limit length
        safe_base = safe_base[:100]
        
        return safe_base + ext.lower()
    
    @staticmethod
    def _validate_and_extract_metadata(media: Media) -> Dict[str, Any]:
        """
        Validate file and extract metadata (e.g., image dimensions).
        
        Args:
            media: Media object
            
        Returns:
            Dict with validation result and metadata
        """
        try:
            # For images, extract dimensions using PIL/Pillow
            if media.mime_type.startswith('image/'):
                try:
                    from PIL import Image
                    
                    with Image.open(media.file.path) as img:
                        width, height = img.size
                        
                        return {
                            'success': True,
                            'width': width,
                            'height': height,
                            'format': img.format
                        }
                except ImportError:
                    logger.warning("PIL/Pillow not installed, skipping image metadata extraction")
                    return {
                        'success': True,
                        'message': 'Image validation skipped (PIL not available)'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Image validation failed: {str(e)}',
                        'error_type': 'image_validation_failed'
                    }
            
            # For other file types, basic validation passed
            return {
                'success': True,
                'message': 'File validated successfully'
            }
            
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    @staticmethod
    def get_user_media(user: Any, content=None, limit: int = 50):
        """
        Get media files for a user.
        
        Args:
            user: User object
            content: Optional Content to filter by
            limit: Maximum number of results
            
        Returns:
            QuerySet of Media objects
        """
        qs = Media.objects.filter(owner=user)
        
        if content:
            qs = qs.filter(content=content)
        
        return qs.order_by('-created_at')[:limit]
    
    @staticmethod
    def delete_media(media_id: int, user: Any) -> Dict[str, Any]:
        """
        Delete a media file (with ownership check).
        
        Args:
            media_id: Media ID
            user: User (for ownership verification)
            
        Returns:
            Dict with success flag
        """
        try:
            media = Media.objects.filter(id=media_id, owner=user).first()
            
            if not media:
                return {
                    'success': False,
                    'error': 'Media not found or unauthorized'
                }
            
            # Delete file from storage
            if media.file:
                media.file.delete(save=False)
            
            # Delete database record
            media.delete()
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Media deletion failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
