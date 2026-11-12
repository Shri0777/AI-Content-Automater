"""Shows saved credentials on the admin site. Encrypted keys are hidden."""

from django.contrib import admin

from credentials.models import ProviderCredential


@admin.register(ProviderCredential)
class ProviderCredentialAdmin(admin.ModelAdmin):
    """How credentials are listed in the admin site."""

    list_display = ["user", "kind", "adapter", "model_name", "key_hint"]
    list_filter = ["kind", "adapter"]
    exclude = ["encrypted_key"]
