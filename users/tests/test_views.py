from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone
from datetime import timedelta

from users.models import UserProfile, PasswordResetToken


class RegistrationViewTest(TestCase):
    """Tests for user registration view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('users:register')

    def test_registration_page_loads(self):
        """Test that registration page loads successfully."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')
        self.assertIn('form', response.context)

    def test_successful_registration(self):
        """Test successful user registration."""
        response = self.client.post(self.url, {
            'email': 'newuser@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123'
        })

        # Should redirect to login
        self.assertRedirects(response, reverse('users:login'))

        # User should be created
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.username, 'newuser@example.com')

        # Profile should be created
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        profile = user.profile
        self.assertEqual(profile.role, 'user')

    def test_registration_password_mismatch(self):
        """Test registration with mismatched passwords."""
        response = self.client.post(self.url, {
            'email': 'newuser@example.com',
            'password1': 'securepass123',
            'password2': 'differentpass123'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('Passwords do not match.', response.content.decode())
        self.assertFalse(User.objects.filter(email='newuser@example.com').exists())

    def test_registration_duplicate_email(self):
        """Test registration with existing email."""
        User.objects.create_user(
            username='existing@example.com',
            email='existing@example.com',
            password='pass123'
        )

        response = self.client.post(self.url, {
            'email': 'existing@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('A user with this email already exists.', response.content.decode())

    def test_registration_weak_password(self):
        """Test registration with weak password (too short)."""
        response = self.client.post(self.url, {
            'email': 'newuser@example.com',
            'password1': 'short',
            'password2': 'short'
        })

        self.assertEqual(response.status_code, 200)
        # Check that form has errors for weak password
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)

    def test_authenticated_user_redirected(self):
        """Test that authenticated users are redirected from registration."""
        user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)


class LoginViewTest(TestCase):
    """Tests for user login view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('users:login')
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

    def test_login_page_loads(self):
        """Test that login page loads successfully."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_successful_login(self):
        """Test successful login."""
        response = self.client.post(self.url, {
            'email': 'test@example.com',
            'password': 'testpass123'
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = self.client.post(self.url, {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        messages = list(response.context['messages'])
        self.assertTrue(any('Invalid email or password' in str(m) for m in messages))

    def test_login_nonexistent_user(self):
        """Test login with non-existent user."""
        response = self.client.post(self.url, {
            'email': 'nonexistent@example.com',
            'password': 'somepassword'
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_case_insensitive_email(self):
        """Test that login is case-insensitive for email."""
        response = self.client.post(self.url, {
            'email': 'TEST@EXAMPLE.COM',
            'password': 'testpass123'
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_authenticated_user_redirected(self):
        """Test that authenticated users are redirected from login."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)


class LogoutViewTest(TestCase):
    """Tests for user logout view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('users:logout')
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_successful_logout(self):
        """Test successful logout."""
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('users:login'))
        # Check user is logged out
        response = self.client.get(reverse('users:login'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post(self):
        """Test that logout requires POST method."""
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    def test_logout_requires_authentication(self):
        """Test that logout requires authentication."""
        response = self.client.post(self.url)

        # Should redirect to login with next parameter
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class PasswordResetRequestViewTest(TestCase):
    """Tests for password reset request view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('users:password_reset')
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_password_reset_page_loads(self):
        """Test that password reset page loads successfully."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset.html')
        self.assertIn('form', response.context)

    def test_password_reset_existing_user(self):
        """Test password reset for existing user."""
        response = self.client.post(self.url, {
            'email': 'test@example.com'
        })

        self.assertRedirects(response, reverse('users:login'))

        # Token should be created
        self.assertTrue(PasswordResetToken.objects.filter(user=self.user).exists())

        # Email should be sent (console backend)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('test@example.com', mail.outbox[0].to)
        self.assertIn('Password Reset', mail.outbox[0].subject)

    def test_password_reset_nonexistent_user(self):
        """Test password reset for non-existent user (timing-safe)."""
        response = self.client.post(self.url, {
            'email': 'nonexistent@example.com'
        })

        # Should still show success message (timing-safe)
        self.assertRedirects(response, reverse('users:login'))

        # No token should be created
        self.assertFalse(
            PasswordResetToken.objects.filter(user__email='nonexistent@example.com').exists()
        )

        # No email should be sent
        self.assertEqual(len(mail.outbox), 0)


class PasswordResetConfirmViewTest(TestCase):
    """Tests for password reset confirmation view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='oldpass123'
        )
        self.token_obj = PasswordResetToken.generate_token(self.user)
        self.url = reverse('users:password_reset_confirm', kwargs={'token': self.token_obj.token})

    def test_password_reset_confirm_page_loads(self):
        """Test that password reset confirm page loads with valid token."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset_confirm.html')
        self.assertIn('form', response.context)

    def test_successful_password_reset(self):
        """Test successful password reset."""
        response = self.client.post(self.url, {
            'password1': 'newsecurepass123',
            'password2': 'newsecurepass123'
        })

        self.assertRedirects(response, reverse('users:login'))

        # Token should be marked as used
        self.token_obj.refresh_from_db()
        self.assertIsNotNone(self.token_obj.used_at)

        # User should be able to login with new password
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newsecurepass123'))

    def test_password_reset_invalid_token(self):
        """Test password reset with invalid token."""
        invalid_url = reverse('users:password_reset_confirm', kwargs={'token': 'invalid_token_12345'})

        response = self.client.get(invalid_url)

        self.assertEqual(response.status_code, 404)

    def test_password_reset_expired_token(self):
        """Test password reset with expired token."""
        self.token_obj.expires_at = timezone.now() - timedelta(minutes=1)
        self.token_obj.save()

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('users:password_reset'))
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any('invalid or has expired' in str(m) for m in messages))

    def test_password_reset_used_token(self):
        """Test password reset with already used token."""
        self.token_obj.mark_as_used()

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('users:password_reset'))

    def test_password_reset_password_mismatch(self):
        """Test password reset with mismatched passwords."""
        response = self.client.post(self.url, {
            'password1': 'newsecurepass123',
            'password2': 'differentpass123'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('Passwords do not match.', response.content.decode())

        # Token should not be marked as used
        self.token_obj.refresh_from_db()
        self.assertIsNone(self.token_obj.used_at)
