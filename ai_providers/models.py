"""
AI Provider models for managing user-specific provider configurations and credentials.

This module implements provider-neutral AI integration allowing users to configure
their own API credentials for text and image generation providers.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet
from django.conf import settings
import base64

User = get_user_model()


class ProviderConfig(models.Model):
    """
    User-specific AI provider configuration.
    
    Stores provider selection and endpoint configuration without credentials.
    Each user can have multiple provider configurations (e.g., text + image).
    """
    
    CAPABILITY_CHOICES = [
        ('text', 'Text Generation'),
        ('image', 'Image Generation'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='provider_configs',
        help_text='User who owns this configuration'
    )
    
    provider_name = models.CharField(
        max_length=100,
        help_text='Provider identifier (e.g., openai, anthropic, together)'
    )
    
    capability = models.CharField(
        max_length=20,
        choices=CAPABILITY_CHOICES,
        help_text='Primary capability this configuration provides'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this configuration is currently active'
    )
    
    endpoint_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Custom API endpoint (optional, provider-specific)'
    )
    
    model_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text='Specific model to use (e.g., gpt-4o, claude-3-5-sonnet)'
    )
    
    configuration = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional provider-specific configuration'
    )
    
    # Validation status
    last_validated = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this configuration was last successfully validated'
    )
    
    validation_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Last validation result'
    )
    
    validation_message = models.TextField(
        null=True,
        blank=True,
        help_text='Detailed validation message'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ai_provider_config'
        unique_together = [['user', 'provider_name', 'capability']]
        indexes = [
            models.Index(fields=['user', 'capability', 'is_active']),
            models.Index(fields=['provider_name']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.provider_name} ({self.capability})"
    
    def get_active_credential(self):
        """Get the active credential for this configuration."""
        return self.credentials.filter(is_active=True).first()


class ProviderCredential(models.Model):
    """
    Encrypted user credentials for AI providers.
    
    Stores API keys and secrets with encryption. Never returned in full via API.
    """
    
    config = models.ForeignKey(
        ProviderConfig,
        on_delete=models.CASCADE,
        related_name='credentials',
        help_text='Associated provider configuration'
    )
    
    credential_name = models.CharField(
        max_length=100,
        default='api_key',
        help_text='Credential type (api_key, secret_key, token, etc.)'
    )
    
    encrypted_value = models.BinaryField(
        help_text='Encrypted credential value'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this credential is currently active'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this credential was last used successfully'
    )
    
    class Meta:
        db_table = 'ai_provider_credential'
        indexes = [
            models.Index(fields=['config', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.config.provider_name} - {self.credential_name} ({'active' if self.is_active else 'inactive'})"
    
    def set_credential(self, value):
        """Encrypt and store the credential value."""
        if not value:
            raise ValidationError("Credential value cannot be empty")
        
        # Get or generate encryption key
        key = self._get_encryption_key()
        fernet = Fernet(key)
        
        # Encrypt the value
        self.encrypted_value = fernet.encrypt(value.encode('utf-8'))
    
    def get_credential(self):
        """Decrypt and return the credential value."""
        if not self.encrypted_value:
            return None
        
        key = self._get_encryption_key()
        fernet = Fernet(key)
        
        try:
            return fernet.decrypt(bytes(self.encrypted_value)).decode('utf-8')
        except Exception:
            return None
    
    def get_masked_value(self):
        """Return a masked version of the credential for display."""
        value = self.get_credential()
        if not value:
            return "••••••••"
        
        # Show first 4 and last 4 characters
        if len(value) <= 12:
            return "••••••••"
        
        return f"{value[:4]}••••••••{value[-4:]}"
    
    @staticmethod
    def _get_encryption_key():
        """Get or generate the encryption key."""
        # Try to get from settings first
        key = getattr(settings, 'CREDENTIAL_ENCRYPTION_KEY', None) or getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
        
        if not key:
            from django.core.exceptions import ImproperlyConfigured
            if __import__('os').environ.get('DJANGO_SETTINGS_MODULE', '').endswith('.production'):
                raise ImproperlyConfigured(
                    'CREDENTIAL_ENCRYPTION_KEY (or FIELD_ENCRYPTION_KEY) must be configured '
                    'with a stable Fernet key before storing or reading provider credentials.'
                )
            # Development-only fallback. Existing credentials encrypted with this key
            # are not portable across process restarts; configure a stable key locally.
            if not hasattr(settings, '_RUNTIME_ENCRYPTION_KEY'):
                settings._RUNTIME_ENCRYPTION_KEY = Fernet.generate_key()
            key = settings._RUNTIME_ENCRYPTION_KEY
        
        # If key is a string, encode it; if bytes, use directly
        if isinstance(key, str):
            try:
                raw = base64.urlsafe_b64decode(key)
                if len(raw) == 32:
                    return key.encode('utf-8')
            except Exception:
                pass
            
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'ai_content_automater_salt',  # Fixed salt for consistency
                iterations=100000,
            )
            return base64.urlsafe_b64encode(kdf.derive(key.encode('utf-8')))
        
        return key
    
    def save(self, *args, **kwargs):
        """Override save to ensure only one active credential per config/name."""
        if self.is_active:
            # Deactivate other credentials with same config and name
            ProviderCredential.objects.filter(
                config=self.config,
                credential_name=self.credential_name,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)
