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


class ContentStatusInfoTests(TestCase):
    """Tests for Content.get_status_info() method (TASK-048)."""

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
            title='Test Content',
            topic='Testing'
        )

    def test_get_status_info_returns_dict(self):
        """Test that get_status_info returns a dictionary."""
        info = self.content.get_status_info()
        self.assertIsInstance(info, dict)

    def test_status_info_contains_required_fields(self):
        """Test that status info contains all required fields."""
        info = self.content.get_status_info()

        required_fields = [
            'lifecycle_state',
            'lifecycle_state_display',
            'current_version_number',
            'version_count',
            'last_state_change_at',
            'available_transitions',
            'created_at',
            'updated_at'
        ]

        for field in required_fields:
            self.assertIn(field, info, f"Missing field: {field}")

    def test_status_info_lifecycle_state(self):
        """Test lifecycle state in status info."""
        self.content.lifecycle_state = 'in_progress'
        self.content.save()

        info = self.content.get_status_info()

        self.assertEqual(info['lifecycle_state'], 'in_progress')
        self.assertEqual(info['lifecycle_state_display'], 'In Progress')

    def test_status_info_version_count_no_versions(self):
        """Test version count when no versions exist."""
        info = self.content.get_status_info()
        self.assertEqual(info['version_count'], 0)
        self.assertIsNone(info['current_version_number'])

    def test_status_info_version_count_with_versions(self):
        """Test version count with multiple versions."""
        v1 = ContentVersion.create_initial_version(
            self.content, self.user, 'V1'
        )
        self.content.current_version = v1
        self.content.save()

        ContentVersion.create_next_version(
            self.content, self.user, 'V2'
        )
        ContentVersion.create_next_version(
            self.content, self.user, 'V3'
        )

        info = self.content.get_status_info()
        self.assertEqual(info['version_count'], 3)
        self.assertEqual(info['current_version_number'], 1)

    def test_status_info_available_transitions_from_draft(self):
        """Test available transitions from draft state."""
        self.content.lifecycle_state = 'draft'
        self.content.save()

        info = self.content.get_status_info()
        self.assertEqual(info['available_transitions'], ['in_progress'])

    def test_status_info_available_transitions_from_in_progress(self):
        """Test available transitions from in_progress state."""
        self.content.lifecycle_state = 'in_progress'
        self.content.save()

        info = self.content.get_status_info()
        self.assertIn('pending_review', info['available_transitions'])
        self.assertIn('draft', info['available_transitions'])

    def test_status_info_available_transitions_from_pending_review(self):
        """Test available transitions from pending_review state."""
        self.content.lifecycle_state = 'pending_review'
        self.content.save()

        info = self.content.get_status_info()
        self.assertIn('approved', info['available_transitions'])
        self.assertIn('draft', info['available_transitions'])

    def test_status_info_available_transitions_from_archived(self):
        """Test that archived state has no available transitions."""
        self.content.lifecycle_state = 'archived'
        self.content.save()

        info = self.content.get_status_info()
        self.assertEqual(info['available_transitions'], [])

    def test_status_info_timestamps(self):
        """Test that timestamps are included and valid."""
        info = self.content.get_status_info()

        self.assertIsNotNone(info['created_at'])
        self.assertIsNotNone(info['updated_at'])
        self.assertIsNotNone(info['last_state_change_at'])

        # last_state_change_at should match updated_at
        self.assertEqual(info['last_state_change_at'], info['updated_at'])


class ContentVersionImmutabilityTests(TestCase):
    """
    Tests for ContentVersion immutability enforcement (TASK-052).

    Verifies that the PostgreSQL trigger prevents updates to snapshot
    fields while allowing legitimate approval metadata updates.
    """

    def setUp(self):
        """Create test user, content, and version."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='Test Content',
            topic='Testing'
        )

        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Original content text'
        )

    def test_version_content_text_cannot_be_updated_via_orm(self):
        """Test that content_text cannot be modified via ORM update()."""
        from django.db import IntegrityError, DatabaseError

        with self.assertRaises((IntegrityError, DatabaseError)) as ctx:
            ContentVersion.objects.filter(pk=self.version.pk).update(
                content_text='Modified text'
            )

        self.assertIn('immutable', str(ctx.exception).lower())

    def test_version_content_text_cannot_be_modified_via_save(self):
        """Test that content_text cannot be modified via instance save()."""
        from django.db import IntegrityError, DatabaseError

        self.version.content_text = 'Changed text'

        with self.assertRaises((IntegrityError, DatabaseError)) as ctx:
            self.version.save()

        self.assertIn('immutable', str(ctx.exception).lower())

    def test_version_number_cannot_be_changed(self):
        """Test that version_number is immutable."""
        from django.db import IntegrityError, DatabaseError

        with self.assertRaises((IntegrityError, DatabaseError)) as ctx:
            ContentVersion.objects.filter(pk=self.version.pk).update(
                version_number=999
            )

        self.assertIn('immutable', str(ctx.exception).lower())

    def test_created_at_cannot_be_changed(self):
        """Test that created_at timestamp is immutable."""
        from django.db import IntegrityError, DatabaseError
        from django.utils import timezone

        new_time = timezone.now() + timezone.timedelta(days=1)

        with self.assertRaises((IntegrityError, DatabaseError)) as ctx:
            ContentVersion.objects.filter(pk=self.version.pk).update(
                created_at=new_time
            )

        self.assertIn('immutable', str(ctx.exception).lower())

    def test_created_by_cannot_be_changed(self):
        """Test that created_by user is immutable."""
        from django.db import IntegrityError, DatabaseError

        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=other_user)

        with self.assertRaises((IntegrityError, DatabaseError)) as ctx:
            ContentVersion.objects.filter(pk=self.version.pk).update(
                created_by=other_user
            )

        self.assertIn('immutable', str(ctx.exception).lower())

    def test_change_summary_cannot_be_modified(self):
        """Test that change_summary is immutable."""
        from django.db import IntegrityError, DatabaseError

        with self.assertRaises((IntegrityError, DatabaseError)) as ctx:
            ContentVersion.objects.filter(pk=self.version.pk).update(
                change_summary='Modified summary'
            )

        self.assertIn('immutable', str(ctx.exception).lower())

    def test_is_approved_CAN_be_updated(self):
        """Test that is_approved CAN be modified (approval workflow)."""
        # This should NOT raise an exception
        self.assertFalse(self.version.is_approved)

        # Update via ORM
        ContentVersion.objects.filter(pk=self.version.pk).update(
            is_approved=True
        )

        # Verify update succeeded
        self.version.refresh_from_db()
        self.assertTrue(self.version.is_approved)

        # Can also update back to False
        ContentVersion.objects.filter(pk=self.version.pk).update(
            is_approved=False
        )

        self.version.refresh_from_db()
        self.assertFalse(self.version.is_approved)

    def test_is_approved_can_be_updated_via_save(self):
        """Test that is_approved can be updated via instance save()."""
        self.assertFalse(self.version.is_approved)

        # Update via save()
        self.version.is_approved = True
        self.version.save(update_fields=['is_approved'])

        # Verify update succeeded
        self.version.refresh_from_db()
        self.assertTrue(self.version.is_approved)

    def test_new_versions_can_be_created(self):
        """Test that creating new versions still works."""
        v2 = ContentVersion.create_next_version(
            content=self.content,
            created_by=self.user,
            content_text='Version 2 text',
            change_summary='Second version'
        )

        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v2.content_text, 'Version 2 text')

    def test_versions_can_be_retrieved(self):
        """Test that reading versions is not affected."""
        retrieved = ContentVersion.objects.get(pk=self.version.pk)

        self.assertEqual(retrieved.content_text, 'Original content text')
        self.assertEqual(retrieved.version_number, 1)

    def test_multiple_versions_all_immutable(self):
        """Test that all versions remain immutable."""
        from django.db import IntegrityError, DatabaseError

        v2 = ContentVersion.create_next_version(
            self.content, self.user, 'Text 2'
        )
        v3 = ContentVersion.create_next_version(
            self.content, self.user, 'Text 3'
        )

        # None can have their content modified
        with self.assertRaises((IntegrityError, DatabaseError)):
            ContentVersion.objects.filter(pk=v2.pk).update(
                content_text='Changed'
            )

        with self.assertRaises((IntegrityError, DatabaseError)):
            ContentVersion.objects.filter(pk=v3.pk).update(
                content_text='Changed'
            )

    def test_combined_update_with_immutable_field_fails(self):
        """Test that updating both mutable and immutable fields fails."""
        from django.db import IntegrityError, DatabaseError, transaction

        original_text = self.version.content_text
        original_approved = self.version.is_approved

        try:
            with transaction.atomic():
                ContentVersion.objects.filter(pk=self.version.pk).update(
                    is_approved=True,
                    content_text='Sneaky change'
                )
            # If we get here, the test should fail
            self.fail("Expected an exception when updating immutable field")
        except (IntegrityError, DatabaseError) as e:
            self.assertIn('immutable', str(e).lower())

        # Verify nothing was updated (need fresh query outside failed transaction)
        self.version = ContentVersion.objects.get(pk=self.version.pk)
        self.assertEqual(self.version.is_approved, original_approved)
        self.assertEqual(self.version.content_text, original_text)
