from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from content.models import Content, ContentVersion
from users.models import UserProfile


class ContentAuthorizationTest(TestCase):
    """Tests for content view-level authorization enforcement."""

    def setUp(self):
        """Create test users and content."""
        # User 1 (content owner)
        self.user1 = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user1)

        # User 2 (unauthorized user)
        self.user2 = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user2)

        # Create content owned by user1
        self.content = Content.objects.create(
            owner=self.user1,
            title='User 1 Content',
            topic='Testing',
            description='Test content'
        )

        # Create initial version
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user1,
            content_text='Initial content text'
        )
        self.content.current_version = self.version
        self.content.save()

        self.client = Client()

    def test_unauthenticated_user_cannot_list_content(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(reverse('content:list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_unauthenticated_user_cannot_view_content_detail(self):
        """Test that unauthenticated users cannot view content details."""
        response = self.client.get(
            reverse('content:detail', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_unauthenticated_user_cannot_create_content(self):
        """Test that unauthenticated users cannot create content."""
        response = self.client.get(reverse('content:create'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_unauthenticated_user_cannot_edit_content(self):
        """Test that unauthenticated users cannot edit content."""
        response = self.client.get(
            reverse('content:edit', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_unauthenticated_user_cannot_delete_content(self):
        """Test that unauthenticated users cannot delete content."""
        response = self.client.post(
            reverse('content:delete', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_unauthorized_user_cannot_view_content(self):
        """Test that authenticated user cannot view another user's content."""
        self.client.force_login(self.user2)

        response = self.client.get(
            reverse('content:detail', kwargs={'pk': self.content.pk})
        )

        # Should return 403 Forbidden, not 404 or 200
        self.assertEqual(response.status_code, 403)
        self.assertIn('permission', response.content.decode().lower())

    def test_unauthorized_user_cannot_edit_content(self):
        """Test that authenticated user cannot edit another user's content."""
        self.client.force_login(self.user2)

        # GET request
        response = self.client.get(
            reverse('content:edit', kwargs={'pk': self.content.pk})
        )
        self.assertEqual(response.status_code, 403)

        # POST request
        response = self.client.post(
            reverse('content:edit', kwargs={'pk': self.content.pk}),
            {
                'title': 'Hacked Title',
                'topic': 'Hacking',
            }
        )
        self.assertEqual(response.status_code, 403)

        # Verify content was not modified
        self.content.refresh_from_db()
        self.assertEqual(self.content.title, 'User 1 Content')
        self.assertEqual(self.content.topic, 'Testing')

    def test_unauthorized_user_cannot_delete_content(self):
        """Test that authenticated user cannot delete another user's content."""
        self.client.force_login(self.user2)

        response = self.client.post(
            reverse('content:delete', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 403)

        # Verify content still exists
        self.assertTrue(Content.objects.filter(pk=self.content.pk).exists())

    def test_unauthorized_user_cannot_view_versions(self):
        """Test that authenticated user cannot view another user's version history."""
        self.client.force_login(self.user2)

        response = self.client.get(
            reverse('content:versions', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_content_id_returns_404(self):
        """Test that invalid content ID returns 404, not 500 or 403."""
        self.client.force_login(self.user2)

        # Try to access non-existent content
        response = self.client.get(
            reverse('content:detail', kwargs={'pk': 99999})
        )

        self.assertEqual(response.status_code, 404)

    def test_manipulated_id_cannot_bypass_ownership(self):
        """Test that URL manipulation cannot bypass ownership checks."""
        # Create another content owned by user2
        user2_content = Content.objects.create(
            owner=self.user2,
            title='User 2 Content',
            topic='User 2 Topic'
        )

        # Login as user1
        self.client.force_login(self.user1)

        # Try to access user2's content
        response = self.client.get(
            reverse('content:detail', kwargs={'pk': user2_content.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_owner_can_view_own_content(self):
        """Test that content owner can view their own content."""
        self.client.force_login(self.user1)

        response = self.client.get(
            reverse('content:detail', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User 1 Content')

    def test_owner_can_edit_own_content(self):
        """Test that content owner can edit their own content."""
        self.client.force_login(self.user1)

        # GET edit page
        response = self.client.get(
            reverse('content:edit', kwargs={'pk': self.content.pk})
        )
        self.assertEqual(response.status_code, 200)

        # POST update
        response = self.client.post(
            reverse('content:edit', kwargs={'pk': self.content.pk}),
            {
                'title': 'Updated Title',
                'topic': 'Updated Topic',
                'description': 'Updated description',
                'lifecycle_state': 'draft',
            }
        )

        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)

        # Verify update
        self.content.refresh_from_db()
        self.assertEqual(self.content.title, 'Updated Title')
        self.assertEqual(self.content.topic, 'Updated Topic')

    def test_owner_can_delete_own_content(self):
        """Test that content owner can delete their own content."""
        self.client.force_login(self.user1)

        content_pk = self.content.pk

        response = self.client.post(
            reverse('content:delete', kwargs={'pk': content_pk})
        )

        # Should redirect to list page
        self.assertEqual(response.status_code, 302)

        # Verify deletion
        self.assertFalse(Content.objects.filter(pk=content_pk).exists())

    def test_owner_can_view_version_history(self):
        """Test that content owner can view version history."""
        self.client.force_login(self.user1)

        response = self.client.get(
            reverse('content:versions', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 200)


class ContentListTest(TestCase):
    """Tests for content list view filtering."""

    def setUp(self):
        """Create test users and content."""
        self.user1 = User.objects.create_user(
            username='user1@example.com',
            email='user1@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user1)

        self.user2 = User.objects.create_user(
            username='user2@example.com',
            email='user2@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user2)

        # User 1 content
        self.user1_content1 = Content.objects.create(
            owner=self.user1,
            title='User 1 Content 1'
        )
        self.user1_content2 = Content.objects.create(
            owner=self.user1,
            title='User 1 Content 2'
        )

        # User 2 content
        self.user2_content1 = Content.objects.create(
            owner=self.user2,
            title='User 2 Content 1'
        )

        self.client = Client()

    def test_user_only_sees_own_content(self):
        """Test that content list is filtered by owner."""
        self.client.force_login(self.user1)

        response = self.client.get(reverse('content:list'))

        self.assertEqual(response.status_code, 200)

        # Should see own content
        self.assertContains(response, 'User 1 Content 1')
        self.assertContains(response, 'User 1 Content 2')

        # Should NOT see other user's content
        self.assertNotContains(response, 'User 2 Content 1')

    def test_list_shows_correct_count_per_user(self):
        """Test that each user sees correct count of their content."""
        # User 1 should see 2 items
        self.client.force_login(self.user1)
        response = self.client.get(reverse('content:list'))
        contents = response.context['contents']
        self.assertEqual(contents.count(), 2)

        # User 2 should see 1 item
        self.client.force_login(self.user2)
        response = self.client.get(reverse('content:list'))
        contents = response.context['contents']
        self.assertEqual(contents.count(), 1)


class ContentCreateTest(TestCase):
    """Tests for content creation authorization."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client = Client()

    def test_created_content_automatically_owned_by_user(self):
        """Test that created content is automatically owned by authenticated user."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('content:create'),
            {
                'title': 'New Content',
                'topic': 'Testing',
                'description': 'Test description',
                'content_text': 'Initial content text',
            }
        )

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Verify content ownership
        content = Content.objects.get(title='New Content')
        self.assertEqual(content.owner, self.user)

        # Verify initial version creator
        self.assertEqual(content.current_version.created_by, self.user)
