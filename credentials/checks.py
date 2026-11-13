"""Check that a saved credential really works ("Test connection").

This lives apart from services.py because it needs the provider classes in
studio/, and studio itself uses credentials.services.
"""

from core.errors import ProviderError, ProviderKeyRejected
from credentials.services import get_user_credential, record_check
from studio.providers import get_provider


def check_credential(user, credential_id):
    """Make a small request with the credential and save how it went.

    Returns the credential, with status "verified", "invalid" (the key was
    refused) or still "unverified" (the provider failed for another reason,
    explained in last_error).
    """
    credential = get_user_credential(user, credential_id)
    provider = get_provider(credential)
    if provider is None:
        record_check(
            credential, "unverified", "This kind of key cannot be checked yet."
        )
        return credential
    try:
        provider.check_connection()
    except ProviderKeyRejected as error:
        record_check(credential, "invalid", str(error))
        return credential
    except ProviderError as error:
        record_check(credential, "unverified", str(error))
        return credential
    record_check(credential, "verified")
    return credential
