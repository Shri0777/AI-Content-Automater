from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from content.models import Content, ContentVersion
from users.models import UserProfile


class ContentModelTest(TestCase):
    """Tests for Content model."""

    def setUp(self):
        """Create test user and profile for each test."""
        self.user = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)

        self.other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.other_user)

    def test_create_content(self):
        """Test creating basic content."""
        content = Content.objects.create(
            owner=self.user,
            title='Test Content',
            topic='Testing',
            description='Test description'
        )

        self.assertEqual(content.owner, self.user)
        self.assertEqual(content.title, 'Test Content')
        self.assertEqual(content.topic, 'Testing')
        self.assertEqual(content.description, 'Test description')
        self.assertEqual(content.lifecycle_state, 'draft')
        self.assertIsNone(content.current_version)
        self.assertIsNotNone(content.created_at)
        self.assertIsNotNone(content.updated_at)
        self.assertIsNone(content.deleted_at)

    def test_content_default_lifecycle_state(self):
        """Test that content defaults to draft state."""
        content = Content.objects.create(
            owner=self.user,
            title='Test Content'
        )

        self.assertEqual(content.lifecycle_state, 'draft')

    def test_content_str_representation(self):
        """Test string representation of Content."""
        content = Content.objects.create(
            owner=self.user,
            title='My Content',
            lifecycle_state='draft'
        )

        self.assertEqual(str(content), 'My Content (Draft)')

    def test_content_ordering(self):
        """Test that content is ordered by created_at descending."""
        content1 = Content.objects.create(owner=self.user, title='First')
        content2 = Content.objects.create(owner=self.user, title='Second')
        content3 = Content.objects.create(owner=self.user, title='Third')

        contents = list(Content.objects.all())
        self.assertEqual(contents[0], content3)  # Most recent first
        self.assertEqual(contents[1], content2)
        self.assertEqual(contents[2], content1)

    def test_content_cascade_delete_on_owner_deletion(self):
        """Test that content is deleted when owner is deleted."""
        content = Content.objects.create(
            owner=self.user,
            title='Test Content'
        )
        content_id = content.id

        self.user.delete()

        self.assertFalse(Content.objects.filter(id=content_id).exists())

    def test_owner_related_name(self):
        """Test accessing user's content via related name."""
        content1 = Content.objects.create(owner=self.user, title='Content 1')
        content2 = Content.objects.create(owner=self.user, title='Content 2')

        user_contents = self.user.contents.all()
        self.assertEqual(user_contents.count(), 2)
        self.assertIn(content1, user_contents)
        self.assertIn(content2, user_contents)

    def test_ownership_isolation(self):
        """Test that users can only see their own content."""
        user1_content = Content.objects.create(
            owner=self.user,
            title='User 1 Content'
        )
        user2_content = Content.objects.create(
            owner=self.other_user,
            title='User 2 Content'
        )

        user1_contents = Content.objects.filter(owner=self.user)
        self.assertEqual(user1_contents.count(), 1)
        self.assertEqual(user1_contents.first(), user1_content)

        user2_contents = Content.objects.filter(owner=self.other_user)
        self.assertEqual(user2_contents.count(), 1)
        self.assertEqual(user2_contents.first(), user2_content)


class ContentLifecycleTest(TestCase):
    """Tests for Content lifecycle state transitions."""

    def setUp(self):
        """Create test user and content."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Test Content'
        )

    def test_valid_transition_draft_to_in_progress(self):
        """Test valid transition from draft to in_progress."""
        self.assertTrue(self.content.can_transition_to('in_progress'))
        self.content.transition_to('in_progress')
        self.assertEqual(self.content.lifecycle_state, 'in_progress')

    def test_valid_transition_in_progress_to_pending_review(self):
        """Test valid transition from in_progress to pending_review."""
        self.content.lifecycle_state = 'in_progress'
        self.content.save()

        self.assertTrue(self.content.can_transition_to('pending_review'))
        self.content.transition_to('pending_review')
        self.assertEqual(self.content.lifecycle_state, 'pending_review')

    def test_valid_transition_pending_review_to_approved(self):
        """Test valid transition from pending_review to approved."""
        self.content.lifecycle_state = 'pending_review'
        self.content.save()

        self.assertTrue(self.content.can_transition_to('approved'))
        self.content.transition_to('approved')
        self.assertEqual(self.content.lifecycle_state, 'approved')

    def test_valid_transition_approved_to_published(self):
        """Test valid transition from approved to published."""
        self.content.lifecycle_state = 'approved'
        self.content.save()

        self.assertTrue(self.content.can_transition_to('published'))
        self.content.transition_to('published')
        self.assertEqual(self.content.lifecycle_state, 'published')

    def test_valid_transition_published_to_archived(self):
        """Test valid transition from published to archived."""
        self.content.lifecycle_state = 'published'
        self.content.save()

        self.assertTrue(self.content.can_transition_to('archived'))
        self.content.transition_to('archived')
        self.assertEqual(self.content.lifecycle_state, 'archived')

    def test_valid_transition_pending_review_to_draft(self):
        """Test revision: pending_review back to draft."""
        self.content.lifecycle_state = 'pending_review'
        self.content.save()

        self.assertTrue(self.content.can_transition_to('draft'))
        self.content.transition_to('draft')
        self.assertEqual(self.content.lifecycle_state, 'draft')

    def test_invalid_transition_draft_to_published(self):
        """Test invalid transition: cannot skip states."""
        self.assertFalse(self.content.can_transition_to('published'))

        with self.assertRaises(ValidationError):
            self.content.transition_to('published')

    def test_invalid_transition_archived_terminal(self):
        """Test that archived is a terminal state."""
        self.content.lifecycle_state = 'archived'
        self.content.save()

        self.assertFalse(self.content.can_transition_to('draft'))
        self.assertFalse(self.content.can_transition_to('published'))

        with self.assertRaises(ValidationError):
            self.content.transition_to('draft')

    def test_transition_updates_timestamp(self):
        """Test that transitions update the updated_at timestamp."""
        original_updated = self.content.updated_at

        self.content.transition_to('in_progress')

        self.assertGreater(self.content.updated_at, original_updated)


class ContentVersionModelTest(TestCase):
    """Tests for ContentVersion model."""

    def setUp(self):
        """Create test user and content."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Test Content'
        )

    def test_create_content_version(self):
        """Test creating a content version."""
        version = ContentVersion.objects.create(
            content=self.content,
            version_number=1,
            content_text='Version 1 text',
            created_by=self.user
        )

        self.assertEqual(version.content, self.content)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.content_text, 'Version 1 text')
        self.assertEqual(version.created_by, self.user)
        self.assertIsNotNone(version.created_at)
        self.assertFalse(version.is_approved)

    def test_version_str_representation(self):
        """Test string representation of ContentVersion."""
        version = ContentVersion.objects.create(
            content=self.content,
            version_number=2,
            created_by=self.user
        )

        self.assertEqual(str(version), 'Test Content v2')

    def test_version_ordering(self):
        """Test that versions are ordered by version_number descending."""
        v1 = ContentVersion.objects.create(
            content=self.content,
            version_number=1,
            created_by=self.user
        )
        v2 = ContentVersion.objects.create(
            content=self.content,
            version_number=2,
            created_by=self.user
        )
        v3 = ContentVersion.objects.create(
            content=self.content,
            version_number=3,
            created_by=self.user
        )

        versions = list(self.content.versions.all())
        self.assertEqual(versions[0], v3)  # Highest version first
        self.assertEqual(versions[1], v2)
        self.assertEqual(versions[2], v1)

    def test_version_unique_together_constraint(self):
        """Test that content + version_number must be unique."""
        ContentVersion.objects.create(
            content=self.content,
            version_number=1,
            created_by=self.user
        )

        # Attempt to create duplicate version number
        with self.assertRaises(IntegrityError):
            ContentVersion.objects.create(
                content=self.content,
                version_number=1,  # Duplicate
                created_by=self.user
            )

    def test_version_cascade_delete_on_content_deletion(self):
        """Test that versions are deleted when content is deleted."""
        v1 = ContentVersion.objects.create(
            content=self.content,
            version_number=1,
            created_by=self.user
        )
        v2 = ContentVersion.objects.create(
            content=self.content,
            version_number=2,
            created_by=self.user
        )

        content_id = self.content.id
        v1_id = v1.id
        v2_id = v2.id

        self.content.delete()

        self.assertFalse(ContentVersion.objects.filter(id=v1_id).exists())
        self.assertFalse(ContentVersion.objects.filter(id=v2_id).exists())

    def test_create_initial_version(self):
        """Test creating initial version via helper method."""
        version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Initial content'
        )

        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.content_text, 'Initial content')
        self.assertEqual(version.content, self.content)

    def test_create_next_version(self):
        """Test creating subsequent versions via helper method."""
        v1 = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Version 1'
        )

        v2 = ContentVersion.create_next_version(
            content=self.content,
            created_by=self.user,
            content_text='Version 2',
            change_summary='Updated content'
        )

        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v2.content_text, 'Version 2')
        self.assertEqual(v2.change_summary, 'Updated content')

    def test_create_next_version_auto_increment(self):
        """Test that next version auto-increments correctly."""
        v1 = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user
        )
        v2 = ContentVersion.create_next_version(
            content=self.content,
            created_by=self.user,
            content_text='V2'
        )
        v3 = ContentVersion.create_next_version(
            content=self.content,
            created_by=self.user,
            content_text='V3'
        )

        self.assertEqual(v1.version_number, 1)
        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v3.version_number, 3)
