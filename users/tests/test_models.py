from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from users.models import UserProfile, PasswordResetToken


class UserProfileModelTest(TestCase):
    """Tests for UserProfile model."""

    def setUp(self):
        """Create test user for each test."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_user_profile(self):
        """Test creating a user profile."""
        profile = UserProfile.objects.create(user=self.user)

        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.role, 'user')  # Default role
        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)

    def test_user_profile_with_administrator_role(self):
        """Test creating profile with administrator role."""
        profile = UserProfile.objects.create(user=self.user, role='administrator')

        self.assertEqual(profile.role, 'administrator')
        self.assertTrue(profile.is_administrator())

    def test_user_profile_is_administrator_false(self):
        """Test is_administrator returns False for regular users."""
        profile = UserProfile.objects.create(user=self.user, role='user')

        self.assertFalse(profile.is_administrator())

    def test_user_profile_str_representation(self):
        """Test string representation of UserProfile."""
        profile = UserProfile.objects.create(user=self.user)

        self.assertEqual(str(profile), 'test@example.com - User')

    def test_user_profile_cascade_delete(self):
        """Test that profile is deleted when user is deleted."""
        profile = UserProfile.objects.create(user=self.user)
        profile_id = profile.id

        self.user.delete()

        self.assertFalse(UserProfile.objects.filter(id=profile_id).exists())

    def test_user_profile_related_name(self):
        """Test accessing profile via user.profile."""
        profile = UserProfile.objects.create(user=self.user)

        self.assertEqual(self.user.profile, profile)


class PasswordResetTokenModelTest(TestCase):
    """Tests for PasswordResetToken model."""

    def setUp(self):
        """Create test user for each test."""
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_generate_token(self):
        """Test generating a password reset token."""
        token_obj = PasswordResetToken.generate_token(self.user)

        self.assertIsNotNone(token_obj.token)
        self.assertEqual(len(token_obj.token), 64)  # hex(32) = 64 chars
        self.assertEqual(token_obj.user, self.user)
        self.assertIsNone(token_obj.used_at)
        self.assertIsNotNone(token_obj.expires_at)

    def test_token_expires_in_30_minutes(self):
        """Test that token expires in 30 minutes."""
        before = timezone.now()
        token_obj = PasswordResetToken.generate_token(self.user)
        after = timezone.now()

        expected_expiry_min = before + timedelta(minutes=30)
        expected_expiry_max = after + timedelta(minutes=30)

        self.assertGreaterEqual(token_obj.expires_at, expected_expiry_min)
        self.assertLessEqual(token_obj.expires_at, expected_expiry_max)

    def test_token_is_valid_when_fresh(self):
        """Test that freshly generated token is valid."""
        token_obj = PasswordResetToken.generate_token(self.user)

        self.assertTrue(token_obj.is_valid())
        self.assertFalse(token_obj.is_expired())

    def test_token_is_invalid_when_used(self):
        """Test that used token is invalid."""
        token_obj = PasswordResetToken.generate_token(self.user)
        token_obj.mark_as_used()

        self.assertFalse(token_obj.is_valid())
        self.assertIsNotNone(token_obj.used_at)

    def test_token_is_invalid_when_expired(self):
        """Test that expired token is invalid."""
        token_obj = PasswordResetToken.generate_token(self.user)
        # Manually set expiry to past
        token_obj.expires_at = timezone.now() - timedelta(minutes=1)
        token_obj.save()

        self.assertTrue(token_obj.is_expired())
        self.assertFalse(token_obj.is_valid())

    def test_mark_as_used(self):
        """Test marking token as used."""
        token_obj = PasswordResetToken.generate_token(self.user)

        self.assertIsNone(token_obj.used_at)

        before = timezone.now()
        token_obj.mark_as_used()
        after = timezone.now()

        self.assertIsNotNone(token_obj.used_at)
        self.assertGreaterEqual(token_obj.used_at, before)
        self.assertLessEqual(token_obj.used_at, after)

    def test_token_uniqueness(self):
        """Test that generated tokens are unique."""
        token1 = PasswordResetToken.generate_token(self.user)
        token2 = PasswordResetToken.generate_token(self.user)

        self.assertNotEqual(token1.token, token2.token)

    def test_token_str_representation_valid(self):
        """Test string representation of valid token."""
        token_obj = PasswordResetToken.generate_token(self.user)

        str_repr = str(token_obj)
        self.assertIn('test@example.com', str_repr)
        self.assertIn('Valid', str_repr)

    def test_token_str_representation_used(self):
        """Test string representation of used token."""
        token_obj = PasswordResetToken.generate_token(self.user)
        token_obj.mark_as_used()

        str_repr = str(token_obj)
        self.assertIn('Used', str_repr)

    def test_token_str_representation_expired(self):
        """Test string representation of expired token."""
        token_obj = PasswordResetToken.generate_token(self.user)
        token_obj.expires_at = timezone.now() - timedelta(minutes=1)
        token_obj.save()

        str_repr = str(token_obj)
        self.assertIn('Expired', str_repr)

    def test_cascade_delete_on_user_deletion(self):
        """Test that tokens are deleted when user is deleted."""
        token_obj = PasswordResetToken.generate_token(self.user)
        token_id = token_obj.id

        self.user.delete()

        self.assertFalse(PasswordResetToken.objects.filter(id=token_id).exists())

    def test_multiple_tokens_per_user(self):
        """Test that a user can have multiple tokens."""
        token1 = PasswordResetToken.generate_token(self.user)
        token2 = PasswordResetToken.generate_token(self.user)

        user_tokens = PasswordResetToken.objects.filter(user=self.user)
        self.assertEqual(user_tokens.count(), 2)
        self.assertIn(token1, user_tokens)
        self.assertIn(token2, user_tokens)
