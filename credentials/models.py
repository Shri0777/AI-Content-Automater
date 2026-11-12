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

# Which providers ("adapters") each kind of credential may use. Real
# providers are added in Phase 3; "demo" is the built-in fake.
ADAPTERS_BY_KIND = {
    "text": ["demo"],
    "image": ["demo"],
    "news": ["demo"],
}


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
