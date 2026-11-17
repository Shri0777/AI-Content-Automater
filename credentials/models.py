"""Database table for the API keys of a user's AI and news providers.

Each user keeps at most one credential of each kind:
    text  - the text model (writes captions and image prompts, reviews posts)
    image - the image model (makes the poster artwork)
    news  - an optional extra news source
The key itself is stored encrypted (see core/crypto.py) and never sent back.
"""

import uuid

from django.conf import settings
from django.db import models

KIND_CHOICES = [
    ("text", "Text model"),
    ("image", "Image model"),
    ("news", "News source"),
]

# Which providers ("adapters") each kind of credential may use. "demo" is
# the built-in fake. The shared news sources need no key (newsroom/presets.py);
# a user's own paid news key is an optional extra, added later.
ADAPTERS_BY_KIND = {
    "text": ["demo", "openai_compatible", "anthropic"],
    "image": ["demo", "openai_compatible", "nvidia_flux", "fal"],
    "news": ["demo"],
}

# These providers cannot work without an API key. (An OpenAI-compatible
# server you run yourself, such as Ollama, may not need one.)
KEY_REQUIRED_ADAPTERS = ["anthropic", "nvidia_flux", "fal"]

STATUS_CHOICES = [
    ("unverified", "Not checked yet"),
    ("verified", "Working"),
    ("invalid", "The provider refused the key"),
]


class ProviderCredential(models.Model):
    """One saved provider and its encrypted API key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    adapter = models.CharField(max_length=40)
    model_name = models.CharField(max_length=200, blank=True)
    base_url = models.URLField(blank=True)
    encrypted_key = models.TextField(blank=True)
    # The last 4 characters of the key, so users can tell keys apart.
    key_hint = models.CharField(max_length=4, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="unverified"
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    # Why the last check or use failed, in plain words (never the key).
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind"], name="one_credential_per_user_and_kind"
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.kind} ({self.adapter})"
