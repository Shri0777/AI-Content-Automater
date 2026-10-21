"""
View tests for research app.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch, MagicMock

from research.models import ResearchProfile, ContentCreationRequest, Research
from users.models import UserProfile

User = get_user_model()


class ResearchProfileViewTests(TestCase):
    """Tests for research profile views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser@example.com', password='testpass123')
        self.profile = ResearchProfile.get_or_create_for_user(self.user)
    
    def test_profile_view_requires_login(self):
        """Test that profile view requires authentication."""
        self.client.logout()
        response = self.client.get(reverse('research:profile_view'))
        self.assertEqual(response.status_code, 302)
    
    def test_profile_view_displays_profile(self):
        """Test that profile view displays user's profile."""
        response = self.client.get(reverse('research:profile_view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Research Profile')
    
    def test_profile_edit_post_updates_profile(self):
        """Test that profile edit form updates the profile."""
        response = self.client.post(reverse('research:profile_edit'), {
            'topics': 'machine learning, data science',
            'audience': 'data scientists',
            'content_goal': 'technical deep dives',
            'freshness_days': 14,
            'language': 'en',
            'source_categories': ['news']
        })
        
        self.assertEqual(response.status_code, 302)
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.topics, ['machine learning', 'data science'])
        self.assertEqual(self.profile.audience, 'data scientists')


class ContentCreationRequestViewTests(TestCase):
    """Tests for content creation request views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser@example.com', password='testpass123')
        self.profile = ResearchProfile.get_or_create_for_user(self.user)
    
    def test_request_new_post_creates_request(self):
        """Test that request creation form creates a request."""
        response = self.client.post(reverse('research:request_new'), {
            'topics': 'kubernetes, containers',
            'audience': 'DevOps engineers',
            'content_goal': 'practical tutorials',
            'freshness_days': 3,
            'language': 'en',
            'source_categories': ['news'],
            'specific_query': 'kubernetes best practices'
        })
        
        self.assertEqual(response.status_code, 302)
        
        request = ContentCreationRequest.objects.filter(user=self.user).first()
        self.assertIsNotNone(request)
        self.assertEqual(request.topics, ['kubernetes', 'containers'])
        self.assertEqual(request.status, 'configuring')
    
    def test_request_detail_displays_request(self):
        """Test that request detail view displays request info."""
        request = ContentCreationRequest.create_from_profile(self.user)
        
        response = self.client.get(reverse('research:request_detail', args=[request.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Research Request')
    
    def test_request_list_displays_requests(self):
        """Test that request list shows user requests."""
        ContentCreationRequest.create_from_profile(self.user)
        
        response = self.client.get(reverse('research:request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Request #')


class ResearchExecutionViewTests(TestCase):
    """Tests for research execution with mocked HTTP."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser@example.com', password='testpass123')
        self.request = ContentCreationRequest.create_from_profile(self.user)
    
    def test_research_select_htmx(self):
        """Test HTMX source selection."""
        research = Research.objects.create(
            owner=self.user,
            creation_request=self.request,
            entry_type='rss',
            title='Test',
            url='https://example.com/test',
            canonical_url='https://example.com/test',
            source_name='Test',
            published_date=timezone.now(),
            overall_score=0.8
        )
        
        # Select with HTMX header
        response = self.client.post(
            reverse('research:research_select', args=[research.pk]),
            {'action': 'select'},
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        
        research.refresh_from_db()
        self.assertTrue(research.is_selected)
