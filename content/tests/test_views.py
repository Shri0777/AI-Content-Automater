from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch

from content.models import Content, ContentVersion
from content.services.buffer_service import BufferPublishingService
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

    def test_forbidden_response_is_a_full_html_document(self):
        """The 403 body must start with a doctype so the browser does not
        fall back to Quirks Mode (observed in a real browser audit)."""
        self.client.force_login(self.user2)

        response = self.client.get(
            reverse('content:detail', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 403)
        body = response.content.decode()
        self.assertTrue(body.lstrip().lower().startswith('<!doctype html>'))
        self.assertIn('You do not have permission to access this content.', body)

    def test_unauthorized_user_cannot_retry_generation(self):
        """A non-owner POSTing the generation-retry action must get 403 and
        must not change the content's generation state."""
        from content.models import Content

        self.content.generation_status = 'failed'
        self.content.save(update_fields=['generation_status'])
        self.client.force_login(self.user2)

        response = self.client.post(
            reverse('content:generate_retry', kwargs={'pk': self.content.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.content.refresh_from_db()
        self.assertEqual(self.content.generation_status, 'failed')

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
        # The Celery broker is not available in tests; mock the enqueue so the
        # assertion below tests ownership on a *successful* enqueue (the real
        # .delay() attempt would correctly mark the draft 'failed').
        self.client.force_login(self.user)

        with patch('content.views.generate_post_from_brief_task') as mock_task:
            response = self.client.post(
                reverse('content:create'),
                {
                    'brief': 'Announce our new AI automation service for small businesses.',
                    'target_channels': [],
                }
            )

        # Should redirect to the generation-status page on success
        self.assertEqual(response.status_code, 302)

        # Verify content ownership and brief persistence
        content = Content.objects.get(title='Announce our new AI automation service for small businesses.')
        self.assertEqual(content.owner, self.user)
        self.assertEqual(content.brief, 'Announce our new AI automation service for small businesses.')
        self.assertEqual(content.target_channels, [])
        self.assertEqual(content.generation_status, 'queued')
        self.assertTrue(mock_task.delay.called)


class ContentCreateValidationTest(TestCase):
    """Regression tests for brief-create validation errors (Bug B).

    Ensures that validation-error re-renders supply every template variable the
    create template requires, including ``buffer_status`` (which previously was
    undefined inside the creation helper and raised NameError).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='validator@example.com',
            email='validator@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    def test_empty_brief_renders_validation_error(self, mock_profiles, mock_status):
        """Empty brief re-renders the form with a readable error (no NameError)."""
        mock_status.return_value = {
            'configured': True, 'connected': True, 'status': 'connected',
            'masked_token': 'buff_...1234'
        }
        mock_profiles.return_value = [
            {'id': 'chan_1', 'service': 'twitter', 'formatted_username': '@tester'}
        ]

        response = self.client.post(
            reverse('content:create'),
            {'brief': '', 'target_channels': ['chan_1']}
        )

        self.assertEqual(response.status_code, 200)
        # The validation error is present in the template context (avoids
        # HTML-escaped apostrophe mismatches in rendered output).
        self.assertEqual(
            response.context['errors']['brief'],
            "Please describe what you'd like to post."
        )
        self.assertContains(response, '@tester')
        # The submitted brief is preserved.
        self.assertContains(response, '')

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    def test_oversized_brief_renders_validation_error(self, mock_profiles, mock_status):
        """Brief over 1,000 characters re-renders the form with a readable error."""
        mock_status.return_value = {
            'configured': True, 'connected': True, 'status': 'connected',
            'masked_token': 'buff_...1234'
        }
        mock_profiles.return_value = []

        long_brief = 'x' * 1001
        response = self.client.post(
            reverse('content:create'),
            {'brief': long_brief, 'target_channels': []}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Brief is too long (maximum 1,000 characters).")
        # Submitted value preserved.
        self.assertContains(response, long_brief[:50])

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    def test_unauthorized_channel_id_rejected(self, mock_profiles, mock_status):
        """A channel ID not in the authorized set is rejected on validation."""
        mock_status.return_value = {
            'configured': True, 'connected': True, 'status': 'connected',
            'masked_token': 'buff_...1234'
        }
        # Only chan_1 is authorized; chan_99 is not.
        mock_profiles.return_value = [
            {'id': 'chan_1', 'service': 'twitter', 'formatted_username': '@tester'}
        ]

        response = self.client.post(
            reverse('content:create'),
            {'brief': 'A valid brief for testing.', 'target_channels': ['chan_99']}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not authorized destinations")

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    @patch('content.views.generate_post_from_brief_task')
    def test_valid_brief_no_channels_redirects(self, mock_task, mock_profiles, mock_status):
        """A valid brief with no channels still creates a draft (drafts may lack
        channels; publishing requires them)."""
        mock_status.return_value = {
            'configured': True, 'connected': True, 'status': 'connected',
            'masked_token': 'buff_...1234'
        }
        mock_profiles.return_value = []

        response = self.client.post(
            reverse('content:create'),
            {'brief': 'A valid brief for testing.', 'target_channels': []}
        )

        self.assertEqual(response.status_code, 302)
        content = Content.objects.get(brief='A valid brief for testing.')
        self.assertEqual(content.owner, self.user)
        self.assertEqual(content.target_channels, [])
        self.assertEqual(content.generation_status, 'queued')

    def test_unauthorized_user_cannot_access_another_users_content(self):
        """Users cannot view or act on content they do not own."""
        other = User.objects.create_user(
            username='other@example.com', email='other@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=other)
        content = Content.objects.create(
            owner=other, brief='Someone else brief', generation_status='queued'
        )

        # Log in as self.user, try to access other's generation-status page.
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('content:generation_status', kwargs={'pk': content.pk})
        )
        self.assertEqual(response.status_code, 403)


class ContentGenerationStatusTest(TestCase):
    """Regression tests for the generation-status page (Bug A).

    Ensures statuses containing underscores render a readable label instead of
    crashing on the removed |replace template filter.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='status@example.com',
            email='status@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def _make_content(self, status):
        return Content.objects.create(
            owner=self.user,
            brief='A brief for status testing.',
            generation_status=status,
        )

    def test_status_with_underscores_renders_readable_label(self):
        """generating_text and generating_posters show readable labels, HTTP 200."""
        for status, expected_label in [
            ('generating_text', 'Generating Text'),
            ('generating_posters', 'Generating Posters'),
            ('queued', 'Queued'),
            ('failed', 'Failed'),
            ('complete', 'Complete'),
            ('partial', 'Partial'),
            ('idle', 'Idle'),
        ]:
            content = self._make_content(status)
            response = self.client.get(
                reverse('content:generation_status', kwargs={'pk': content.pk})
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, expected_label)
            # The raw internal status value must not leak as a template error.
            self.assertNotContains(response, 'TemplateSyntaxError')
            self.assertNotContains(response, 'Invalid filter')

    def test_unknown_status_degrades_gracefully(self):
        """An unrecognized status does not crash the page."""
        content = self._make_content('weird_state_xyz')
        response = self.client.get(
            reverse('content:generation_status', kwargs={'pk': content.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Weird State Xyz')

    def test_failed_content_shows_retry_action(self):
        """Failed generation retains the retry button."""
        content = self._make_content('failed')
        response = self.client.get(
            reverse('content:generation_status', kwargs={'pk': content.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Try again')
        self.assertContains(
            response,
            reverse('content:generate_retry', kwargs={'pk': content.pk})
        )

    def test_heading_matches_actual_state(self):
        """The page heading must not claim generation is in progress when it
        failed or finished (Bug: failed drafts were headed 'being prepared')."""
        heading_by_status = {
            'failed': 'Generation didn’t finish',
            'complete': 'Your post is ready',
            'queued': 'Your post is being prepared',
            'generating_text': 'Your post is being prepared',
        }
        for status, expected_heading in heading_by_status.items():
            with self.subTest(status=status):
                content = self._make_content(status)
                response = self.client.get(
                    reverse('content:generation_status', kwargs={'pk': content.pk})
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_heading)
                if status == 'failed':
                    # A failed draft must not be described as in-progress.
                    self.assertNotContains(response, 'being prepared')
                    # The brief must be clearly labelled, not glued to the
                    # failure sentence.
                    self.assertContains(response, 'Your brief:')

    def test_failed_alert_labels_the_brief(self):
        """The failed alert presents the brief as labelled context."""
        content = self._make_content('failed')
        response = self.client.get(
            reverse('content:generation_status', kwargs={'pk': content.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'We couldn’t generate your post.')
        self.assertContains(response, 'Your brief: A brief for status testing.')


class CeleryEnqueueFailureTest(TestCase):
    """Regression tests for Celery enqueue failures (Bug: stuck 'queued').

    A draft must never stay 'queued' when no task was actually enqueued:
    the retry view only accepts 'failed'/'partial', so a 'queued' draft with
    a failed enqueue would be permanently stuck with no working retry.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='enqueue@example.com',
            email='enqueue@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    @patch('content.views.generate_post_from_brief_task')
    def test_initial_enqueue_failure_marks_failed(
        self, mock_task, mock_profiles, mock_status
    ):
        """When .delay() raises on creation, the draft persists as 'failed'."""
        mock_status.return_value = {'configured': False, 'connected': False}
        mock_profiles.return_value = []
        mock_task.delay.side_effect = Exception("broker unavailable")

        response = self.client.post(
            reverse('content:create'),
            {'brief': 'A brief whose enqueue will fail.', 'target_channels': []},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        content = Content.objects.get(brief='A brief whose enqueue will fail.')
        # The draft is preserved, but no longer falsely 'queued'.
        self.assertEqual(content.owner, self.user)
        self.assertEqual(content.generation_status, 'failed')
        # The user is told generation did not start (message renders via the
        # global toast container as an alert-error).
        self.assertContains(response, 'Could not start generation')
        self.assertContains(response, 'Generation failed. You can try again.')

    @patch.object(BufferPublishingService, 'get_connection_status')
    @patch.object(BufferPublishingService, 'get_profiles')
    @patch('content.views.generate_post_from_brief_task')
    def test_successful_initial_enqueue_keeps_queued(
        self, mock_task, mock_profiles, mock_status
    ):
        """A successful enqueue keeps the existing 'queued' behavior."""
        mock_status.return_value = {'configured': False, 'connected': False}
        mock_profiles.return_value = []

        response = self.client.post(
            reverse('content:create'),
            {'brief': 'A brief that enqueues fine.', 'target_channels': []},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        content = Content.objects.get(brief='A brief that enqueues fine.')
        self.assertEqual(content.generation_status, 'queued')
        self.assertTrue(mock_task.delay.called)

    @patch('content.views.generate_post_from_brief_task')
    def test_retry_enqueue_failure_restores_failed(self, mock_task):
        """When retry .delay() raises, the draft goes back to 'failed'."""
        content = Content.objects.create(
            owner=self.user,
            brief='A failed draft to retry.',
            generation_status='failed',
        )
        mock_task.delay.side_effect = Exception("broker unavailable")

        response = self.client.post(
            reverse('content:generate_retry', kwargs={'pk': content.pk}),
        )

        self.assertEqual(response.status_code, 302)
        content.refresh_from_db()
        # 'queued' must not stick — that would block every further retry.
        self.assertEqual(content.generation_status, 'failed')

    @patch('content.views.generate_post_from_brief_task')
    def test_retry_enqueue_failure_then_success_succeeds(self, mock_task):
        """After a failed retry, a later successful retry becomes 'queued'."""
        content = Content.objects.create(
            owner=self.user,
            brief='A draft retried twice.',
            generation_status='failed',
        )
        mock_task.delay.side_effect = Exception("broker unavailable")

        # First retry fails to enqueue...
        self.client.post(reverse('content:generate_retry', kwargs={'pk': content.pk}))
        content.refresh_from_db()
        self.assertEqual(content.generation_status, 'failed')

        # ...then the broker recovers and the retry succeeds.
        mock_task.delay.side_effect = None
        response = self.client.post(
            reverse('content:generate_retry', kwargs={'pk': content.pk}),
        )
        self.assertEqual(response.status_code, 302)
        content.refresh_from_db()
        self.assertEqual(content.generation_status, 'queued')

    @patch('content.views.generate_post_from_brief_task')
    def test_successful_retry_enqueue_sets_queued(self, mock_task):
        """A successful retry marks the draft 'queued' (existing behavior)."""
        content = Content.objects.create(
            owner=self.user,
            brief='A failed draft retried successfully.',
            generation_status='failed',
        )

        response = self.client.post(
            reverse('content:generate_retry', kwargs={'pk': content.pk}),
        )

        self.assertEqual(response.status_code, 302)
        content.refresh_from_db()
        self.assertEqual(content.generation_status, 'queued')
        self.assertTrue(mock_task.delay.called)

    @patch('content.views.generate_post_from_brief_task')
    def test_retry_rejects_nonowner(self, mock_task):
        """Authorization stays intact: only the owner can retry a draft."""
        other = User.objects.create_user(
            username='notowner@example.com',
            email='notowner@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=other)
        content = Content.objects.create(
            owner=other,
            brief='Someone else\'s failed draft.',
            generation_status='failed',
        )

        response = self.client.post(
            reverse('content:generate_retry', kwargs={'pk': content.pk}),
        )

        self.assertEqual(response.status_code, 403)
        # Nothing was touched and no task enqueued.
        content.refresh_from_db()
        self.assertEqual(content.generation_status, 'failed')
        self.assertFalse(mock_task.delay.called)
