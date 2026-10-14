from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets


class UserProfile(models.Model):
    """
    Extended user profile with business fields.
    Uses OneToOne relationship with Django's built-in User model.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('administrator', 'Administrator'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.get_role_display()}"

    def is_administrator(self):
        """Check if user has administrator role."""
        return self.role == 'administrator'


class PasswordResetToken(models.Model):
    """
    Time-limited, single-use password reset tokens.
    Tokens expire after 30 minutes and can only be used once.
    """
    token = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'password_reset_token'
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f"Token for {self.user.email} - {'Used' if self.used_at else 'Valid' if not self.is_expired() else 'Expired'}"

    @classmethod
    def generate_token(cls, user):
        """
        Generate a new password reset token for the user.
        Token expires in 30 minutes.
        """
        token = secrets.token_hex(32)  # 64 character hex string
        expires_at = timezone.now() + timezone.timedelta(minutes=30)
        return cls.objects.create(
            token=token,
            user=user,
            expires_at=expires_at
        )

    def is_expired(self):
        """Check if token has expired."""
        return timezone.now() > self.expires_at

    def is_valid(self):
        """Check if token is valid (not used and not expired)."""
        return self.used_at is None and not self.is_expired()

    def mark_as_used(self):
        """Mark token as used (single-use enforcement)."""
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])
