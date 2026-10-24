"""
Tests for image generation views.
"""
from unittest.mock import Mock, patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from content.models import Content, Media

User = get_user_model()


class ImageGenerationViewTests(TestCase):
    """Test image generation view integration."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        self.content = Content.objects.create(
            owner=self.user,
            title='Test Content',
            topic='Testing',
            lifecycle_state='draft'
        )
        self.client.login(username='test@example.com', password='testpass123')

    @patch('content.views.image_generation_views.ImageGenerationService.generate_image_for_content')
    def test_generate_image_success(self, mock_generate):
        """Test successful image generation."""
        # Mock successful generation
        mock_media = Mock()
        mock_media.pk = 1
        mock_media.file.url = '/media/test.png'
        mock_generate.return_value = {
            'success': True,
            'media': mock_media,
            'provider': 'NVIDIA FLUX'
        }

        response = self.client.post(
            reverse('content:generate_image', args=[self.content.pk]),
            {'prompt': 'A beautiful sunset over mountains'}
        )

        self.assertEqual(response.status_code, 302)  # Redirect
        mock_generate.assert_called_once()

    @patch('content.views.image_generation_views.ImageGenerationService.generate_image_for_content')
    def test_generate_image_missing_prompt(self, mock_generate):
        """Test image generation with missing prompt."""
        response = self.client.post(
            reverse('content:generate_image', args=[self.content.pk]),
            {'prompt': ''}
        )

        self.assertEqual(response.status_code, 302)  # Redirect with error
        mock_generate.assert_not_called()

    @patch('content.views.image_generation_views.ImageGenerationService.generate_image_for_content')
    def test_generate_image_provider_error(self, mock_generate):
        """Test image generation with provider error."""
        mock_generate.return_value = {
            'success': False,
            'error': 'Provider unavailable',
            'error_type': 'provider_error'
        }

        response = self.client.post(
            reverse('content:generate_image', args=[self.content.pk]),
            {'prompt': 'Test prompt'}
        )

        self.assertEqual(response.status_code, 302)
        mock_generate.assert_called_once()

    def test_generate_image_requires_authentication(self):
        """Test that image generation requires authentication."""
        self.client.logout()
        response = self.client.post(
            reverse('content:generate_image', args=[self.content.pk]),
            {'prompt': 'Test prompt'}
        )

        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('/auth/login/', response.url)

    def test_generate_image_requires_ownership(self):
        """Test that only content owner can generate images."""
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='testpass123'
        )
        self.client.login(username='other@example.com', password='testpass123')

        response = self.client.post(
            reverse('content:generate_image', args=[self.content.pk]),
            {'prompt': 'Test prompt'}
        )

        self.assertEqual(response.status_code, 404)  # Not found (ownership check)

    @patch('content.views.image_generation_views.ImageGenerationService.generate_image_for_content')
    def test_generate_image_htmx_request(self, mock_generate):
        """Test HTMX request returns JSON."""
        mock_media = Mock()
        mock_media.pk = 1
        mock_media.file.url = '/media/test.png'
        mock_generate.return_value = {
            'success': True,
            'media': mock_media,
            'provider': 'NVIDIA FLUX'
        }

        response = self.client.post(
            reverse('content:generate_image', args=[self.content.pk]),
            {'prompt': 'Test prompt'},
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['media_id'], 1)
