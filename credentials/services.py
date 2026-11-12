"""Save, find and remove a user's provider credentials."""

from core.crypto import decrypt_text, encrypt_text
from core.errors import AppError
from credentials.models import ProviderCredential


class CredentialNotFound(AppError):
    """Raised when a credential does not exist or belongs to someone else."""

    status = 404
    code = "not_found"
    title = "Not found"


class CredentialMissing(AppError):
    """Raised when a feature needs a provider the user has not set up."""

    status = 400
    code = "credential_missing"
    title = "Provider not set up"


def save_credential(user, details):
    """Save the user's credential for one kind, replacing any older one.

    details is a dict with kind, adapter, and optionally model_name,
    base_url and api_key.
    """
    credential = ProviderCredential.objects.filter(
        user=user, kind=details["kind"]
    ).first()
    if credential is None:
        credential = ProviderCredential(user=user, kind=details["kind"])
    credential.adapter = details["adapter"]
    credential.model_name = details.get("model_name", "")
    credential.base_url = details.get("base_url", "")
    api_key = details.get("api_key", "")
    credential.encrypted_key = ""
    credential.key_hint = ""
    if api_key:
        credential.encrypted_key = encrypt_text(api_key)
        credential.key_hint = api_key[-4:]
    credential.save()
    return credential


def get_credential(user, kind):
    """Return the user's credential of one kind, or None if there is none."""
    return ProviderCredential.objects.filter(user=user, kind=kind).first()


def require_credential(user, kind):
    """Return the user's credential of one kind, or raise CredentialMissing."""
    credential = get_credential(user, kind)
    if credential is None:
        raise CredentialMissing(
            f"Add a {kind} provider on the credentials page before generating."
        )
    return credential


def read_api_key(credential):
    """Return the plain API key of a credential ("" if it has none)."""
    if not credential.encrypted_key:
        return ""
    return decrypt_text(credential.encrypted_key)


def delete_credential(user, credential_id):
    """Delete one of the user's credentials."""
    credential = ProviderCredential.objects.filter(id=credential_id, user=user).first()
    if credential is None:
        raise CredentialNotFound("That credential does not exist.")
    credential.delete()
