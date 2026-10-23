"""
Tests for campaign, notification, media, and analytics views.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

from content.models import (
    Campaign, CampaignExecution, Content, ContentVersion,
    Notification, NotificationPreference, Media,
    ContentPublication, PublicationMetrics
)

User = get_user_model()


class CampaignViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_campaign_list_requires_auth(self):
        """Unauthenticated user cannot access campaign list."""
        self.client.logout()
        response = self.client.get(reverse('content:campaign_list'))
        self.assertEqual(response.status_code, 302)
        
    def test_campaign_list_view(self):
        """Authenticated user can view their campaigns."""
        Campaign.objects.create(
            owner=self.user,
            name='Test Campaign',
            topic='Testing',
            frequency='weekly',
            start_date=timezone.now().date()
        )
        response = self.client.get(reverse('content:campaign_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Campaign')
        
    def test_campaign_create_get(self):
        """Campaign create page loads."""
        response = self.client.get(reverse('content:campaign_create'))
        self.assertEqual(response.status_code, 200)
        
    def test_campaign_create_post(self):
        """User can create a campaign."""
        response = self.client.post(reverse('content:campaign_create'), {
            'name': 'New Campaign',
            'topic': 'New Topic',
            'frequency': 'daily',
            'generation_instructions': 'Test instructions',
            'start_date': timezone.now().date().isoformat()
        })
        self.assertEqual(Campaign.objects.count(), 1)
        campaign = Campaign.objects.first()
        self.assertEqual(campaign.name, 'New Campaign')
        self.assertEqual(campaign.owner, self.user)
        
    def test_campaign_detail_view(self):
        """Campaign detail view shows campaign information."""
        campaign = Campaign.objects.create(
            owner=self.user,
            name='Detail Test',
            topic='Testing',
            start_date=timezone.now().date()
        )
        response = self.client.get(
            reverse('content:campaign_detail', kwargs={'pk': campaign.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Test')
        
    def test_campaign_detail_unauthorized(self):
        """User cannot view another user's campaign."""
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pass123'
        )
        campaign = Campaign.objects.create(
            owner=other_user,
            name='Other Campaign',
            topic='Testing',
            start_date=timezone.now().date()
        )
        response = self.client.get(
            reverse('content:campaign_detail', kwargs={'pk': campaign.id})
        )
        self.assertEqual(response.status_code, 404)
        
    def test_campaign_activate(self):
        """User can activate a draft campaign."""
        campaign = Campaign.objects.create(
            owner=self.user,
            name='Activation Test',
            topic='Testing',
            status='draft',
            start_date=timezone.now().date()
        )
        response = self.client.post(
            reverse('content:campaign_activate', kwargs={'pk': campaign.id})
        )
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'active')
        self.assertIsNotNone(campaign.next_execution)


class NotificationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_notification_list_requires_auth(self):
        """Unauthenticated user cannot access notifications."""
        self.client.logout()
        response = self.client.get(reverse('content:notification_list'))
        self.assertEqual(response.status_code, 302)
        
    def test_notification_list_view(self):
        """User can view their notifications."""
        Notification.objects.create(
            user=self.user,
            notification_type='content_approved',
            title='Test Notification',
            message='Test message'
        )
        response = self.client.get(reverse('content:notification_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Notification')
        
    def test_notification_ownership(self):
        """User only sees their own notifications."""
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pass123'
        )
        Notification.objects.create(
            user=other_user,
            notification_type='content_approved',
            title='Other Notification',
            message='Other message'
        )
        response = self.client.get(reverse('content:notification_list'))
        self.assertNotContains(response, 'Other Notification')
        
    def test_mark_notification_read(self):
        """User can mark notification as read."""
        notification = Notification.objects.create(
            user=self.user,
            notification_type='content_approved',
            title='Test',
            message='Test',
            is_read=False
        )
        response = self.client.post(
            reverse('content:notification_mark_read', kwargs={'pk': notification.id})
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        
    def test_notification_preferences_view(self):
        """User can view notification preferences."""
        response = self.client.get(reverse('content:notification_preferences'))
        self.assertEqual(response.status_code, 200)
        
    def test_notification_preferences_update(self):
        """User can update notification preferences."""
        response = self.client.post(reverse('content:notification_preferences'), {
            'email_enabled': 'on',
            'in_app_enabled': 'on'
        })
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.email_enabled)
        self.assertTrue(prefs.in_app_enabled)


class MediaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_media_list_requires_auth(self):
        """Unauthenticated user cannot access media list."""
        self.client.logout()
        response = self.client.get(reverse('content:media_list'))
        self.assertEqual(response.status_code, 302)
        
    def test_media_list_view(self):
        """User can view their media library."""
        response = self.client.get(reverse('content:media_list'))
        self.assertEqual(response.status_code, 200)
        
    def test_media_upload_get(self):
        """Media upload page loads."""
        response = self.client.get(reverse('content:media_upload'))
        self.assertEqual(response.status_code, 200)
        
    def test_media_upload_post(self):
        """User can upload media file."""
        # Create a simple test image
        image_content = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        uploaded_file = SimpleUploadedFile(
            'test.png',
            image_content,
            content_type='image/png'
        )
        
        response = self.client.post(reverse('content:media_upload'), {
            'file': uploaded_file
        })
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Media.objects.count(), 1)
        media = Media.objects.first()
        self.assertEqual(media.owner, self.user)
        
    def test_media_detail_view(self):
        """User can view media details."""
        media = Media.objects.create(
            owner=self.user,
            file_name='test.png',
            file_size=1024,
            mime_type='image/png'
        )
        response = self.client.get(
            reverse('content:media_detail', kwargs={'pk': media.id})
        )
        self.assertEqual(response.status_code, 200)
        
    def test_media_ownership(self):
        """User cannot view another user's media."""
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pass123'
        )
        media = Media.objects.create(
            owner=other_user,
            file_name='other.png',
            file_size=1024,
            mime_type='image/png'
        )
        response = self.client.get(
            reverse('content:media_detail', kwargs={'pk': media.id})
        )
        self.assertEqual(response.status_code, 404)


class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
    def test_analytics_dashboard_requires_auth(self):
        """Unauthenticated user cannot access analytics."""
        self.client.logout()
        response = self.client.get(reverse('content:analytics_dashboard'))
        self.assertEqual(response.status_code, 302)
        
    def test_analytics_dashboard_view(self):
        """User can view analytics dashboard."""
        response = self.client.get(reverse('content:analytics_dashboard'))
        self.assertEqual(response.status_code, 200)
        
    def test_analytics_with_data(self):
        """Analytics displays user's content data."""
        # Create test content
        content = Content.objects.create(
            owner=self.user,
            title='Test Content',
            topic='Testing',
            lifecycle_state='published'
        )
        
        # Create content version
        version = ContentVersion.objects.create(
            content=content,
            version_number=1,
            content_text='Test body',
            created_by=self.user
        )
        content.current_version = version
        content.save()
        
        # Create publication
        ContentPublication.objects.create(
            content=content,
            content_version=version,
            user=self.user,
            provider='linkedin',
            status='published'
        )
        
        response = self.client.get(reverse('content:analytics_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Should show content in analytics
        
    def test_analytics_publishing_view(self):
        """User can view publishing analytics."""
        response = self.client.get(reverse('content:analytics_publishing'))
        self.assertEqual(response.status_code, 200)
        
    def test_analytics_campaigns_view(self):
        """User can view campaign analytics."""
        response = self.client.get(reverse('content:analytics_campaigns'))
        self.assertEqual(response.status_code, 200)
