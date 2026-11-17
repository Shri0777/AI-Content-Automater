"""Background jobs for linked social accounts."""

from celery import shared_task

from social.tokens import refresh_expiring_accounts


@shared_task
def refresh_social_tokens_task():
    """Refresh tokens that end soon and warn about ones that cannot be."""
    return refresh_expiring_accounts()
