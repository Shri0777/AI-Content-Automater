"""
Notification Service for creating and delivering user notifications (FR-038).

Handles in-app notifications and optional email delivery based on user preferences.
"""
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from content.models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for creating and delivering user notifications.
    """
    
    @staticmethod
    def create_notification(
        user: Any,
        notification_type: str,
        title: str,
        message: str,
        content=None,
        campaign=None,
        send_email: bool = True
    ) -> Dict[str, Any]:
        """
        Create a notification for a user.
        
        Args:
            user: User to notify
            notification_type: Type of notification (must match model choices)
            title: Notification title
            message: Notification message body
            content: Optional related Content object
            campaign: Optional related Campaign object
            send_email: Whether to attempt email delivery
            
        Returns:
            Dict with success flag and notification object
        """
        try:
            # Create notification record
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                content=content,
                campaign=campaign,
                delivery_status='created'
            )
            
            # Check user preferences
            prefs = NotificationPreference.objects.filter(user=user).first()
            if not prefs:
                # Create default preferences
                prefs = NotificationPreference.objects.create(user=user)
            
            # Deliver in-app notification (always create the record)
            notification.delivered_at = timezone.now()
            notification.delivery_status = 'delivered'
            notification.save(update_fields=['delivered_at', 'delivery_status'])
            
            # Attempt email delivery if enabled
            if send_email and prefs.email_enabled:
                email_result = NotificationService._send_email_notification(
                    user=user,
                    notification=notification
                )
                if not email_result['success']:
                    logger.warning(
                        f"Email delivery failed for notification {notification.id}: "
                        f"{email_result.get('error')}"
                    )
            
            return {
                'success': True,
                'notification': notification
            }
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    @staticmethod
    def _send_email_notification(user: Any, notification: Notification) -> Dict[str, Any]:
        """
        Send email for a notification.
        
        Args:
            user: User to email
            notification: Notification object
            
        Returns:
            Dict with success flag
        """
        try:
            subject = f"[AI Content Automater] {notification.title}"
            message = f"{notification.message}\n\n"
            
            if notification.content:
                message += f"Content: {notification.content.title}\n"
            
            if notification.campaign:
                message += f"Campaign: {notification.campaign.name}\n"
            
            message += "\nLog in to view details: {}/".format(
                getattr(settings, 'SITE_URL', 'http://localhost:8000')
            )
            
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False
            )
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    @staticmethod
    def mark_as_read(notification_id: int, user: Any) -> Dict[str, Any]:
        """
        Mark a notification as read.
        
        Args:
            notification_id: Notification ID
            user: User (for ownership verification)
            
        Returns:
            Dict with success flag
        """
        try:
            notification = Notification.objects.filter(
                id=notification_id,
                user=user
            ).first()
            
            if not notification:
                return {
                    'success': False,
                    'error': 'Notification not found or unauthorized'
                }
            
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            
            return {
                'success': True,
                'notification': notification
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    @staticmethod
    def get_user_notifications(user: Any, unread_only: bool = False, limit: int = 50):
        """
        Get notifications for a user.
        
        Args:
            user: User object
            unread_only: Only return unread notifications
            limit: Maximum number of notifications to return
            
        Returns:
            QuerySet of Notification objects
        """
        qs = Notification.objects.filter(user=user)
        
        if unread_only:
            qs = qs.filter(is_read=False)
        
        return qs[:limit]
